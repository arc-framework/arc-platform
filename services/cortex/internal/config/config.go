package config

import (
	"fmt"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Config is the root configuration for Cortex.
type Config struct {
	Server    ServerConfig    `mapstructure:"server"`
	Telemetry TelemetryConfig `mapstructure:"telemetry"`
	Bootstrap BootstrapConfig `mapstructure:"bootstrap"`
}

type ServerConfig struct {
	Port            int           `mapstructure:"port"`
	ReadTimeout     time.Duration `mapstructure:"read_timeout"`
	WriteTimeout    time.Duration `mapstructure:"write_timeout"`
	ShutdownTimeout time.Duration `mapstructure:"shutdown_timeout"`
}

type TelemetryConfig struct {
	OTLPEndpoint string `mapstructure:"otlp_endpoint"`
	OTLPInsecure bool   `mapstructure:"otlp_insecure"`
	ServiceName  string `mapstructure:"service_name"`
	LogLevel     string `mapstructure:"log_level"`
}

type BootstrapConfig struct {
	RetryBackoff time.Duration  `mapstructure:"retry_backoff"`
	Timeout      time.Duration  `mapstructure:"timeout"`
	Postgres     PostgresConfig `mapstructure:"postgres"`
	NATS         NATSConfig     `mapstructure:"nats"`
	Pulsar       PulsarConfig   `mapstructure:"pulsar"`
	Redis        RedisConfig    `mapstructure:"redis"`
}

type PostgresConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	User     string `mapstructure:"user"`
	Password string `mapstructure:"password"`
	DB       string `mapstructure:"db"`
	SSLMode  string `mapstructure:"ssl_mode"`
	MaxConns int32  `mapstructure:"max_conns"`
}

type NATSConfig struct {
	URL string `mapstructure:"url"`
}

type PulsarConfig struct {
	AdminURL   string `mapstructure:"admin_url"`
	ServiceURL string `mapstructure:"service_url"`
	Tenant     string `mapstructure:"tenant"`
}

type RedisConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
}

// Load reads config from the optional YAML file at path, then overlays
// environment variables with the CORTEX_ prefix (e.g. CORTEX_SERVER_PORT).
func Load(path string) (*Config, error) {
	v := viper.New()

	setDefaults(v)

	v.SetEnvPrefix("CORTEX")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	if path != "" {
		v.SetConfigFile(path)
		if err := v.ReadInConfig(); err != nil {
			return nil, fmt.Errorf("reading config file %s: %w", path, err)
		}
	}

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("unmarshalling config: %w", err)
	}

	return &cfg, nil
}

func setDefaults(v *viper.Viper) {
	v.SetDefault("server.port", 8081)
	v.SetDefault("server.read_timeout", 10*time.Second)
	v.SetDefault("server.write_timeout", 10*time.Second)
	v.SetDefault("server.shutdown_timeout", 30*time.Second)

	v.SetDefault("telemetry.otlp_endpoint", "arc-friday-collector:4317")
	v.SetDefault("telemetry.otlp_insecure", true)
	v.SetDefault("telemetry.service_name", "arc-cortex")
	v.SetDefault("telemetry.log_level", "info")

	v.SetDefault("bootstrap.retry_backoff", 2*time.Second)
	v.SetDefault("bootstrap.timeout", 5*time.Minute)

	v.SetDefault("bootstrap.postgres.host", "arc-oracle")
	v.SetDefault("bootstrap.postgres.port", 5432)
	v.SetDefault("bootstrap.postgres.user", "arc")
	v.SetDefault("bootstrap.postgres.db", "arc_db")
	v.SetDefault("bootstrap.postgres.ssl_mode", "disable")
	v.SetDefault("bootstrap.postgres.max_conns", 25)

	v.SetDefault("bootstrap.nats.url", "nats://arc-flash:4222")

	v.SetDefault("bootstrap.pulsar.admin_url", "http://arc-strange:8080")
	v.SetDefault("bootstrap.pulsar.service_url", "pulsar://arc-strange:6650")
	v.SetDefault("bootstrap.pulsar.tenant", "arc-system")

	v.SetDefault("bootstrap.redis.host", "arc-sonic")
	v.SetDefault("bootstrap.redis.port", 6379)
	v.SetDefault("bootstrap.redis.db", 0)
}
