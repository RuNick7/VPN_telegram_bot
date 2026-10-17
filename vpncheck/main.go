// vpncheck connects to every server in a subscription the way the client
// app does and writes down what happened, one log per server.
//
//	vpncheck https://sub.example.com/api/sub/XXXX   check a subscription
//	vpncheck ABCD-EFGH-JKLM                         check and send the report to a support ticket
//	vpncheck                                        ask for either
//
// See README.md.
package main

import (
	"bufio"
	"context"
	"errors"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/check"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/redact"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/report"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/source"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/subscription"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/ticket"
)

// Set at build time (build.sh).
var (
	version     = "dev"
	defaultSite = ""
)

type listFlag []string

func (l *listFlag) String() string     { return strings.Join(*l, ", ") }
func (l *listFlag) Set(v string) error { *l = append(*l, v); return nil }

type options struct {
	subs    listFlag
	code    string
	site    string
	out     string
	ua      string
	only    string
	list    bool
	yes     bool
	speed   int
	pings   int
	timeout time.Duration
	// An operator's run (operator.go).
	agents string
	env    string
	notify bool
	keep   int
}

var stdin = bufio.NewReader(os.Stdin)

func main() {
	check.ServeWorker()
	os.Exit(run())
}

func run() int {
	var opts options
	flag.Var(&opts.subs, "sub", "ссылка подписки, файл с подпиской или ссылка vless://, hysteria2://... (можно несколько раз)")
	flag.StringVar(&opts.code, "code", "", "код из поддержки: отчёт уйдёт в ваше обращение")
	flag.StringVar(&opts.site, "site", defaultSite, "адрес сайта, куда отправлять отчёт по коду")
	flag.StringVar(&opts.out, "out", "vpncheck-logs", "папка для отчётов")
	flag.StringVar(&opts.ua, "ua", subscription.DefaultUserAgent, "User-Agent для запроса подписки")
	flag.StringVar(&opts.only, "only", "", "проверить только серверы, в адресе или профиле которых есть эта строка")
	flag.BoolVar(&opts.list, "list", false, "только показать серверы, не проверять")
	flag.BoolVar(&opts.yes, "yes", false, "отправить отчёт по коду, не спрашивая")
	flag.IntVar(&opts.speed, "speed", 0, "замерить скорость, скачав через каждый сервер столько МБ (0 — не замерять)")
	flag.IntVar(&opts.pings, "pings", 3, "сколько раз пинговать через каждый сервер")
	flag.DurationVar(&opts.timeout, "timeout", 10*time.Second, "сколько ждать каждого ответа")
	flag.StringVar(&opts.agents, "agents", "", "для админа: строки агентов на нодах, как в NODE_LOG_AGENTS — тогда в отчёт попадут и логи нод")
	flag.StringVar(&opts.env, "env", "", "для админа: .env бота, откуда взять NODE_LOG_AGENTS, ADMIN_BOT_TOKEN и ADMIN_IDS")
	flag.BoolVar(&opts.notify, "notify", false, "для админа: прислать итог и report.txt в чаты ADMIN_IDS через админ-бота")
	flag.IntVar(&opts.keep, "keep", 0, "удалять отчёты старше стольких дней (0 — не удалять)")
	showVersion := flag.Bool("version", false, "показать версию")
	flag.Usage = usage
	flag.Parse()

	if *showVersion {
		fmt.Printf("vpncheck %s (Xray %s, %s/%s)\n", version, check.XrayVersion(), runtime.GOOS, runtime.GOARCH)
		return 0
	}

	// Started by double-click: nothing on the command line, a console window
	// that closes the moment the program ends. Ask, and wait before exiting.
	interactive := flag.NArg() == 0 && len(opts.subs) == 0 && opts.code == ""
	if interactive {
		defer pause()
	}

	for _, arg := range flag.Args() {
		if code, ok := ticket.NormalizeCode(arg); ok {
			opts.code = code
		} else {
			opts.subs = append(opts.subs, arg)
		}
	}
	if interactive {
		fmt.Printf("vpncheck %s — проверка серверов VPN\n\n", version)
		fmt.Println("Вставьте ссылку на подписку или код из поддержки и нажмите Enter.")
		answer := ask("> ")
		if code, ok := ticket.NormalizeCode(answer); ok {
			opts.code = code
		} else if answer != "" {
			opts.subs = append(opts.subs, answer)
		} else {
			usage()
			return 2
		}
	}

	op, err := loadOperator(opts.agents, opts.env)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if opts.notify && (op.token == "" || len(op.chats) == 0) {
		fmt.Fprintln(os.Stderr, "Для -notify нужны ADMIN_BOT_TOKEN и ADMIN_IDS: укажите .env бота через -env или задайте их в окружении.")
		return 2
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	var session *ticket.Session
	var client *ticket.Client
	if opts.code != "" {
		code, ok := ticket.NormalizeCode(opts.code)
		if !ok {
			fmt.Fprintf(os.Stderr, "Код %q не похож на код из поддержки: в нём 12 букв и цифр, например ABCD-EFGH-JKLM.\n", opts.code)
			return 2
		}
		opts.code = code
		if opts.site == "" {
			fmt.Fprintln(os.Stderr, "Не указан сайт для отправки отчёта: запустите с -site https://адрес-сайта")
			return 2
		}
		client = ticket.New(opts.site)
		var err error
		session, err = client.Open(ctx, opts.code)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Код не принят: %v\n", err)
			return 2
		}
		fmt.Printf("Код принят: обращение #%d «%s».\n", session.TicketID, session.Subject)
		if session.SubscriptionURL != "" && len(opts.subs) == 0 {
			opts.subs = append(opts.subs, session.SubscriptionURL)
		}
		if len(opts.subs) == 0 {
			if !interactive {
				fmt.Fprintln(os.Stderr, "Сайт не смог выдать ссылку на подписку: укажите её сами через -sub.")
				return 2
			}
			fmt.Println("Не получилось взять ссылку на подписку автоматически. Вставьте её из бота или личного кабинета:")
			if link := ask("> "); link != "" {
				opts.subs = append(opts.subs, link)
			} else {
				return 2
			}
		}
	}

	return checkAll(ctx, opts, op, session, client, interactive)
}

// checkAll is the run itself, once it is known what to check and where the
// report goes.
func checkAll(ctx context.Context, opts options, op *operator, session *ticket.Session, client *ticket.Client, interactive bool) int {
	red := redact.New()
	if opts.code != "" {
		red.Add(opts.code)
	}
	rep := report.New(version)

	var targets []*subscription.Target
	var profiles []subscription.Profile
	for _, sub := range opts.subs {
		src, found := source.Load(ctx, sub, opts.ua, red)
		rep.Sources = append(rep.Sources, src)
		if src.Error != "" {
			fmt.Printf("Подписка %s: %s\n", red.String(src.URL), red.String(src.Error))
		} else {
			fmt.Printf("Подписка %s: %s, профилей %d, серверов %d\n",
				red.String(src.URL), src.Format, src.Profiles, src.Servers)
		}
		profiles = append(profiles, found...)
	}
	targets = subscription.Targets(profiles)
	if opts.only != "" {
		targets = filter(targets, opts.only)
	}
	rep.Total = len(targets)

	if opts.list {
		for i, target := range targets {
			fmt.Printf("%3d  %-34s %-32s %s\n", i+1, target.Endpoint(), target.Kind(), strings.Join(target.Profiles, ", "))
		}
		return 0
	}

	options := check.DefaultOptions()
	options.Timeout = opts.timeout
	options.Pings = max(1, opts.pings)
	options.SpeedBytes = int64(opts.speed) << 20

	fmt.Println("\nПроверяю соединение без VPN…")
	options.RunID = rep.RunID
	rep.Baseline, rep.Clock = check.Baseline(ctx, options)
	for _, step := range rep.Baseline {
		fmt.Printf("  %-10s %s — %s\n", step.Status, step.Name, step.Detail)
		if step.Name == "Другой VPN" {
			fmt.Println("\n  Выключите VPN-приложение (Happ и другие) и запустите проверку снова — иначе проверяется не сервер, а ваш VPN.")
		}
	}

	if len(targets) > 0 {
		fmt.Printf("\nПроверяю серверов: %d. Сначала сеть до всех сразу, потом подключение к каждому по очереди.\n\n", len(targets))
		rep.Results = check.NewRunner(options).Run(ctx, targets, func(i int, result *check.Result) {
			line := fmt.Sprintf("[%d/%d] %-34s %-30s %s", i+1, len(targets), result.Target.Endpoint(), result.Target.Kind(), result.Verdict)
			if best := result.Best(); best > 0 {
				line += fmt.Sprintf(", пинг %d мс", best.Milliseconds())
			}
			if result.Cause != "" {
				line += " — " + result.Cause
			}
			fmt.Println(red.String(line))
		})
	} else {
		fmt.Println("\nВ подписке не нашлось ни одного сервера.")
	}
	rep.Finished = time.Now()
	if ctx.Err() != nil {
		fmt.Println("\nПроверка прервана, сохраняю то, что успел.")
	}
	// Node lines hold the address the check came from, so they never go into
	// a report sent to a ticket: only an operator's own run asks for them.
	if session == nil && len(op.agents) > 0 && len(rep.Results) > 0 && ctx.Err() == nil {
		fmt.Printf("\nСпрашиваю логи у нод: %d…\n", len(op.agents))
		rep.Nodes = askNodes(ctx, rep, op.agents)
		for _, node := range rep.Nodes {
			if node.Error != "" {
				fmt.Printf("  %-12s не ответила: %s\n", node.Name, node.Error)
				continue
			}
			found := 0
			for _, section := range node.Sections {
				if section.Attributed {
					found++
				}
			}
			fmt.Printf("  %-12s нашла проверку для серверов: %d\n", node.Name, found)
		}
	}

	files, err := report.Write(opts.out, rep, red)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Не удалось сохранить отчёт: %v\n", err)
		return 2
	}
	dir, _ := filepath.Abs(files.Dir)
	fmt.Printf("\n%s\n", red.String(report.OneLine(rep)))
	fmt.Printf("Отчёт сохранён в папке %s\n", dir)
	fmt.Printf("  summary.txt — итог по всем серверам, report.txt — всё в одном файле, servers/ — лог каждого сервера.\n")
	fmt.Println("  Ключи, пароли, идентификаторы и ссылка на подписку в отчёте заменены на [скрыто:…].")

	if session != nil {
		send(ctx, opts, session, client, rep, files, interactive)
	}
	if opts.notify {
		if errs := notify(ctx, op, notifyCaption(rep), files.Full); len(errs) > 0 {
			for _, err := range errs {
				fmt.Fprintf(os.Stderr, "Не удалось отправить итог в Telegram: %v\n", err)
			}
		} else {
			fmt.Printf("Итог отправлен в Telegram: чатов %d.\n", len(op.chats))
		}
	}
	if opts.keep > 0 {
		if removed, err := prune(opts.out, opts.keep, time.Now()); err != nil {
			fmt.Fprintf(os.Stderr, "Не удалось удалить старые отчёты: %v\n", err)
		} else if removed > 0 {
			fmt.Printf("Удалено старых отчётов: %d.\n", removed)
		}
	}

	for _, result := range rep.Results {
		if result.Verdict != check.Works {
			return 1
		}
	}
	if len(rep.Results) < rep.Total || rep.Total == 0 {
		return 1
	}
	return 0
}

// send asks once more, now that the report exists and can be read, and
// only then uploads it.
func send(ctx context.Context, opts options, session *ticket.Session, client *ticket.Client, rep *report.Report, files *report.Files, interactive bool) {
	full, _ := filepath.Abs(files.Full)
	if !opts.yes {
		if !interactive && !isTerminal() {
			fmt.Printf("\nОтчёт не отправлен: подтвердить отправку некому. Запустите с -yes или приложите %s к обращению сами.\n", full)
			return
		}
		fmt.Printf("\nВ обращение #%d «%s» уйдёт файл:\n  %s\nЕго можно открыть и посмотреть перед отправкой.\n", session.TicketID, session.Subject, full)
		answer := strings.ToLower(ask("Отправить? Введите «да» или «нет»: "))
		if answer != "да" && answer != "д" && answer != "y" && answer != "yes" {
			fmt.Println("Не отправлено. Отчёт остался только на этом компьютере.")
			return
		}
	}
	summary := fmt.Sprintf("Отчёт проверки серверов (vpncheck %s): %s", version, report.OneLine(rep))
	uctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 3*time.Minute)
	defer cancel()
	if err := client.Upload(uctx, opts.code, summary, files.Full); err != nil {
		var siteErr *ticket.Error
		if errors.As(err, &siteErr) && siteErr.Status == http.StatusConflict {
			fmt.Printf("Не отправлено: %v\n", err)
		} else {
			fmt.Printf("Не удалось отправить: %v\nПриложите %s к обращению на сайте сами.\n", err, full)
		}
		return
	}
	fmt.Printf("Отчёт отправлен в обращение #%d. Поддержка ответит там же.\n", session.TicketID)
}

func filter(targets []*subscription.Target, needle string) []*subscription.Target {
	needle = strings.ToLower(needle)
	var kept []*subscription.Target
	for _, target := range targets {
		haystack := strings.ToLower(target.Endpoint() + " " + target.Kind() + " " + strings.Join(target.Profiles, " "))
		if strings.Contains(haystack, needle) {
			kept = append(kept, target)
		}
	}
	return kept
}

func ask(prompt string) string {
	fmt.Print(prompt)
	line, _ := stdin.ReadString('\n')
	return strings.TrimSpace(line)
}

func pause() {
	if !isTerminal() {
		return
	}
	fmt.Print("\nНажмите Enter, чтобы закрыть окно.")
	_, _ = stdin.ReadString('\n')
}

func isTerminal() bool {
	info, err := os.Stdin.Stat()
	return err == nil && info.Mode()&os.ModeCharDevice != 0
}

func usage() {
	fmt.Fprintf(os.Stderr, `vpncheck %s — подключается к каждому серверу подписки так же, как приложение, и сохраняет лог по каждому.

Запуск:
  vpncheck https://адрес-подписки        проверить подписку
  vpncheck ABCD-EFGH-JKLM                проверить и отправить отчёт в обращение (код даёт бот поддержки)
  vpncheck                               спросить, что проверять

Для админа, с логами нод и итогом в админ-чат:
  vpncheck -env /opt/tg_vpn/.env -notify -keep 30 -sub URL1 -sub URL2

Перед проверкой выключите VPN-приложение.

Параметры:
`, version)
	flag.PrintDefaults()
}
