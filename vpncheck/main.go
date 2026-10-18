// vpncheck connects to every server in a subscription the way the client
// app does and writes down what happened, one log per server.
//
//	vpncheck https://sub.example.com/api/sub/XXXX         check a subscription
//	vpncheck -send https://sub.example.com/api/sub/XXXX   check and send the report to support
//	vpncheck                                              ask for a link
//
// See README.md.
package main

import (
	"bufio"
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"

	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/redact"
	"github.com/RuNick7/vpn-check/internal/report"
	"github.com/RuNick7/vpn-check/internal/site"
	"github.com/RuNick7/vpn-check/internal/source"
	"github.com/RuNick7/vpn-check/internal/subscription"
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
	send    bool
	note    string
	site    string
	out     string
	ua      string
	only    string
	list    bool
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
	flag.BoolVar(&opts.send, "send", false, "после проверки отправить отчёт в поддержку: он придёт в ваше открытое обращение или откроет новое")
	flag.StringVar(&opts.note, "note", "", "с -send: коротко, что не работает")
	flag.StringVar(&opts.site, "site", defaultSite, "адрес сайта, куда отправлять отчёт")
	flag.StringVar(&opts.out, "out", "vpncheck-logs", "папка для отчётов")
	flag.StringVar(&opts.ua, "ua", subscription.DefaultUserAgent, "User-Agent для запроса подписки")
	flag.StringVar(&opts.only, "only", "", "проверить только серверы, в адресе или профиле которых есть эта строка")
	flag.BoolVar(&opts.list, "list", false, "только показать серверы, не проверять")
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
	interactive := flag.NArg() == 0 && len(opts.subs) == 0
	if interactive {
		defer pause()
	}

	opts.subs = append(opts.subs, flag.Args()...)
	if interactive {
		fmt.Printf("vpncheck %s — проверка серверов VPN\n\n", version)
		fmt.Println("Вставьте ссылку на подписку и нажмите Enter.")
		answer := ask("> ")
		if answer == "" {
			usage()
			return 2
		}
		opts.subs = append(opts.subs, answer)
	}
	if opts.send {
		if opts.site == "" {
			fmt.Fprintln(os.Stderr, "Не указан сайт для отправки отчёта: запустите с -site https://адрес-сайта")
			return 2
		}
		if _, ok := sendable(opts.subs); !ok {
			fmt.Fprintln(os.Stderr, "С -send проверяется одна подписка по ссылке https://…: по ней сайт находит, чей это отчёт.")
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

	return checkAll(ctx, opts, op, interactive)
}

// sendable is the one subscription link a report can be sent with: the site
// finds the customer by it.
func sendable(subs []string) (string, bool) {
	if len(subs) != 1 {
		return "", false
	}
	link := strings.TrimSpace(subs[0])
	lower := strings.ToLower(link)
	return link, strings.HasPrefix(lower, "https://") || strings.HasPrefix(lower, "http://")
}

// checkAll is the run itself, once it is known what to check and where the
// report goes.
func checkAll(ctx context.Context, opts options, op *operator, interactive bool) int {
	red := redact.New()
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
	if !opts.send && !interactive && len(op.agents) > 0 && len(rep.Results) > 0 && ctx.Err() == nil {
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

	if opts.send || (interactive && opts.site != "" && isTerminal()) {
		send(ctx, opts, rep, files, interactive)
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

// send uploads the report to support. With -send that was decided on the
// command line; a double-clicked run asks, now that the report exists and
// can be read first.
func send(ctx context.Context, opts options, rep *report.Report, files *report.Files, interactive bool) {
	link, ok := sendable(opts.subs)
	if !ok || len(rep.Nodes) > 0 {
		return
	}
	full, _ := filepath.Abs(files.Full)
	note := opts.note
	if !opts.send {
		fmt.Printf("\nОтчёт можно отправить в поддержку: он придёт в ваше открытое обращение или откроет новое.\n"+
			"Это файл %s — его можно открыть и посмотреть перед отправкой.\n", full)
		answer := strings.ToLower(ask("Отправить? Введите «да» или «нет»: "))
		if answer != "да" && answer != "д" && answer != "y" && answer != "yes" {
			fmt.Println("Не отправлено. Отчёт остался только на этом компьютере.")
			return
		}
		note = ask("Коротко, что не работает (можно пропустить, нажав Enter): ")
	}
	summary := fmt.Sprintf("Отчёт проверки серверов (vpncheck %s): %s", version, report.OneLine(rep))
	sctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 3*time.Minute)
	defer cancel()
	sent, err := site.New(opts.site).Send(sctx, link, summary, note, files.Full)
	if err != nil {
		var siteErr *site.Error
		if errors.As(err, &siteErr) && siteErr.Message != "" {
			fmt.Printf("Не отправлено: %v\n", err)
		} else {
			fmt.Printf("Не удалось отправить: %v\nПриложите %s к обращению сами.\n", err, full)
		}
		return
	}
	fmt.Printf("Отправлено в обращение №%d. Ответ придёт в бота и в личный кабинет.\n", sent.TicketID)
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
  vpncheck https://адрес-подписки          проверить подписку
  vpncheck -send https://адрес-подписки    проверить и отправить отчёт в поддержку
  vpncheck                                 спросить ссылку

Для админа, с логами нод и итогом в админ-чат:
  vpncheck -env /opt/tg_vpn/.env -notify -keep 30 -sub URL1 -sub URL2

Перед проверкой выключите VPN-приложение.

Параметры:
`, version)
	flag.PrintDefaults()
}
