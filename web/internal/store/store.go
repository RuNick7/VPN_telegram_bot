// Package store is the website's only route to Postgres.
//
// The FastAPI backend this replaces had no database access of its own: it
// shelled out to `python -c "import user_bot..."` once per request. That is
// gone -- the site owns a real connection pool and talks to the same schema
// the bots use.
//
// One rule governs how it shares that schema, and it is enforced by what this
// package does not expose: the site may insert a *pending* payment and read a
// payment's status, and may never move a payment out of pending. That
// transition belongs exclusively to the Python webhook handler, which is the
// only place that verifies a payment against YooKassa before crediting it.
// See payments.go.
package store

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Store struct {
	pool *pgxpool.Pool
}

func Open(ctx context.Context, databaseURL string) (*Store, error) {
	cfg, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		return nil, fmt.Errorf("parse DATABASE_URL: %w", err)
	}
	cfg.MaxConns = 10
	cfg.MaxConnLifetime = time.Hour

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("connect to postgres: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping postgres: %w", err)
	}
	return &Store{pool: pool}, nil
}

func (s *Store) Close() { s.pool.Close() }

// Pool exposes the underlying pool for health checks.
func (s *Store) Pool() *pgxpool.Pool { return s.pool }
