package check

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/RuNick7/vpn-check/internal/subscription"
)

// Each server's tunnel runs in a process of its own: this same binary,
// started again with workerEnv set. Xray keeps state for the whole process
// -- one log handler, and a gRPC connection pool that goes on redialling a
// dead server after its instance is closed -- so in one process every later
// server's log picked up the earlier servers' retries, and those retries
// kept knocking on the earlier nodes for the rest of the run. A process
// that exits takes all of it with it.
const workerEnv = "VPNCHECK_TUNNEL_WORKER"

// ServeWorker does the tunnel stage and exits, when this process was started
// as a worker; otherwise it returns at once. Call it first thing in main,
// and in TestMain of a test binary that runs tunnels.
func ServeWorker() {
	if os.Getenv(workerEnv) != "1" {
		return
	}
	// Whatever a library prints must not land in the answer on stdout.
	out := os.Stdout
	os.Stdout = os.Stderr
	os.Exit(serveWorker(os.Stdin, out))
}

type workerRequest struct {
	Outbound map[string]any
	Chain    []map[string]any
	Options  Options
	Marker   string
}

type workerAnswer struct {
	Steps      []Step
	Pings      []time.Duration
	Exit       map[string]string
	Mbps       float64
	Cause      string
	Log        []string
	MarkerSent bool
}

func serveWorker(in io.Reader, out io.Writer) int {
	var req workerRequest
	if err := json.NewDecoder(in).Decode(&req); err != nil {
		fmt.Fprintln(os.Stderr, "vpncheck worker:", err)
		return 2
	}
	result := &Result{Target: &subscription.Target{Outbound: req.Outbound, Chain: req.Chain}, Marker: req.Marker}
	NewRunner(req.Options).tunnelHere(context.Background(), result)
	answer := workerAnswer{
		Steps: result.Steps, Pings: result.Pings, Exit: result.Exit, Mbps: result.Mbps,
		Cause: result.Cause, Log: result.Log, MarkerSent: result.MarkerSent,
	}
	if err := json.NewEncoder(out).Encode(answer); err != nil {
		fmt.Fprintln(os.Stderr, "vpncheck worker:", err)
		return 2
	}
	return 0
}

// workerLimit is the longest a tunnel stage can take by its own timeouts,
// plus room: past it the worker is stuck and is stopped.
func (r *Runner) workerLimit() time.Duration {
	requests := r.opts.Pings + 2 + len(r.opts.Probes)
	if r.opts.SpeedBytes > 0 {
		requests += 6
	}
	return time.Duration(requests)*r.opts.Timeout + 30*time.Second
}

// tunnel runs the tunnel stage for one server in a worker process.
func (r *Runner) tunnel(ctx context.Context, result *Result) {
	answer, err := r.runWorker(ctx, workerRequest{
		Outbound: result.Target.Outbound, Chain: result.Target.Chain, Options: r.opts, Marker: result.Marker,
	})
	if err != nil {
		if ctx.Err() != nil {
			return
		}
		result.Cause = "проверка через сервер не запустилась: " + err.Error()
		result.add(Step{Name: StepPing, Status: Fail, Detail: result.Cause})
		return
	}
	result.Steps = append(result.Steps, answer.Steps...)
	result.Pings, result.Exit, result.Mbps = answer.Pings, answer.Exit, answer.Mbps
	result.Cause, result.Log, result.MarkerSent = answer.Cause, answer.Log, answer.MarkerSent
}

func (r *Runner) runWorker(ctx context.Context, req workerRequest) (*workerAnswer, error) {
	exe, err := os.Executable()
	if err != nil {
		return nil, err
	}
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	wctx, cancel := context.WithTimeout(ctx, r.workerLimit())
	defer cancel()
	cmd := exec.CommandContext(wctx, exe)
	cmd.Env = append(os.Environ(), workerEnv+"=1")
	cmd.Stdin = bytes.NewReader(body)
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	cmd.WaitDelay = 5 * time.Second
	runErr := cmd.Run()
	var answer workerAnswer
	if err := json.Unmarshal(stdout.Bytes(), &answer); err != nil {
		if runErr == nil {
			runErr = err
		}
		if errors.Is(wctx.Err(), context.DeadlineExceeded) {
			runErr = fmt.Errorf("не уложилась в %s", r.workerLimit())
		}
		if tail := lastLine(stderr.String()); tail != "" {
			runErr = fmt.Errorf("%w: %s", runErr, tail)
		}
		return nil, runErr
	}
	return &answer, nil
}

func lastLine(s string) string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	return strings.TrimSpace(lines[len(lines)-1])
}
