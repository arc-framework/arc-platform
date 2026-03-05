// Package main is the entry point for the arc-cortex bootstrap service.
//
// @title          A.R.C. Cortex API
// @version        1.0
// @description    Cortex bootstrap service — provisions Postgres, NATS, Pulsar, and Redis, then exposes a health/status HTTP API.
// @host           localhost:8801
// @BasePath       /
// @schemes        http
package main

func main() {
	Execute()
}
