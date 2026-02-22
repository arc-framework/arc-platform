package clients

import (
	"time"

	"github.com/sony/gobreaker"
)

// NewCircuitBreaker returns a gobreaker configured to trip after 3 consecutive
// failures and reset after 30 seconds in the open state.
func NewCircuitBreaker(name string) *gobreaker.CircuitBreaker {
	return gobreaker.NewCircuitBreaker(gobreaker.Settings{
		Name:        name,
		MaxRequests: 1,
		Interval:    0,
		Timeout:     30 * time.Second,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			return counts.ConsecutiveFailures >= 3
		},
	})
}
