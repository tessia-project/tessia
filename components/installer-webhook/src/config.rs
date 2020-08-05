// Copyright 2020 IBM Corp.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use serde::Deserialize;
use serde_yaml;

use log::LevelFilter;
use log4rs::append::console::ConsoleAppender;
use log4rs::append::rolling_file::policy::compound;
use log4rs::append::rolling_file::RollingFileAppender;
use log4rs::config::{Appender, Logger, Root};
use log4rs::encode::pattern::PatternEncoder;

use log::{error, info};

/// Application configuration
///
/// Contains settings for servers and logging.
/// Can be loaded from a YAML string or file (within 1st-level section)
#[derive(Deserialize, PartialEq, Debug)]
pub struct Config {
    #[serde(default = "default_log_path")]
    pub log_path: String,

    #[serde(default = "default_webhook_port")]
    pub webhook_port: u16,

    #[serde(default = "default_control_port")]
    pub control_port: u16,

    #[serde(default = "default_cleanup_interval")]
    pub cleanup_interval: u32,

    #[serde(default = "default_log_rotate_size")]
    pub log_rotate_size: u64,

    #[serde(default = "default_log_rotate_keep")]
    pub log_rotate_keep: u32,
}

fn default_log_path() -> String {
    "/var/log/tessia".to_owned()
}
fn default_webhook_port() -> u16 {
    7223
}
fn default_control_port() -> u16 {
    7224
}
fn default_cleanup_interval() -> u32 {
    600
}
fn default_log_rotate_size() -> u64 {
    50 * 1024 * 1024
}
fn default_log_rotate_keep() -> u32 {
    3
}

impl Config {
    pub fn default() -> Self {
        serde_yaml::from_str("{}").unwrap()
    }

    /// Load configuration from yaml file
    pub fn from_yaml_file(filename: &str, section: &str) -> Self {
        info!(
            "Loading configuration from {}, section '{}'",
            filename, section
        );
        match std::fs::read_to_string(filename) {
            Ok(conf) => Config::from_yaml_string(&conf, section),
            Err(_) => {
                error!("Could not load configuration file at {}", filename);
                info!("Using default configuration");
                Config::default()
            }
        }
    }

    /// Load configuration from a string representing well-formed yaml
    pub fn from_yaml_string(yaml_string: &str, section: &str) -> Self {
        match serde_yaml::from_str::<serde_yaml::Value>(yaml_string) {
            Ok(yaml_config) => {
                if section == "" {
                    return serde_yaml::from_value(yaml_config).unwrap_or_else(|e| {
                        error!("Malformed YAML: {}", e);
                        info!("Using default configuration");
                        Config::default()
                    });
                } else if let Some(subsection) = yaml_config.get(section) {
                    return serde_yaml::from_value(subsection.to_owned()).unwrap_or_else(|e| {
                        error!("Could not parse section {}: {}", section, e);
                        info!("Using default configuration");
                        Config::default()
                    });
                } else {
                    error!("Could not find section {} in configuration file", section);
                }
            }
            Err(e) => {
                error!("Could not parse configuration file: {}", e);
            }
        }
        info!("Using default configuration");
        Config::default()
    }

    /// Get safe looger configuration (stdout only)
    pub fn get_safe_looger_config() -> log4rs::config::Config {
        let stdout = ConsoleAppender::builder()
            .encoder(Box::new(PatternEncoder::new(
                "{d(%Y-%m-%d %H:%M:%S)} {l} {t}:{L} - {m}{n}",
            )))
            .build();
        log4rs::config::Config::builder()
            .appender(Appender::builder().build("stdout", Box::new(stdout)))
            .build(Root::builder().appender("stdout").build(LevelFilter::Info))
            .unwrap()
    }

    /// Get log4rs configuration
    pub fn get_logger_config(&self) -> log4rs::config::Config {
        // log file path and format
        let request_log_path = self.log_path.clone() + "/installer-webhook-requests.log";
        const PATTERN: &'static str = "{d(%Y-%m-%d %H:%M:%S)} {l} {t}:{L} - {m}{n}";

        // create stdout configuration section
        let stdout = ConsoleAppender::builder()
            .encoder(Box::new(PatternEncoder::new(PATTERN)))
            .build();
        let mut config_builder = log4rs::config::Config::builder()
            .appender(Appender::builder().build("stdout", Box::new(stdout)));
        let root_builder = log4rs::config::Root::builder().appender("stdout");

        // create rolling requests log
        let roller: Box<dyn compound::roll::Roll> =
            match compound::roll::fixed_window::FixedWindowRoller::builder().build(
                // naming of rolled (archived) log files
                &(request_log_path.clone() + ".{}"),
                // keep this many rotated files
                self.log_rotate_keep,
            ) {
                Ok(r) => Box::new(r),
                Err(e) => {
                    warn!("Could not create rolling request logs: {}", e);
                    info!("Using single file request log");
                    Box::new(compound::roll::delete::DeleteRoller::new())
                }
            };

        match RollingFileAppender::builder()
            .encoder(Box::new(PatternEncoder::new(PATTERN)))
            .build(
                // name of primary requests log file
                &request_log_path,
                Box::new(compound::CompoundPolicy::new(
                    // roll every this many bytes
                    Box::new(compound::trigger::size::SizeTrigger::new(self.log_rotate_size)),
                    roller,
                )),
            ) {
            Ok(request_log) => {
                // apply rolling log configuration to a "requests" logger
                config_builder = config_builder
                    .appender(Appender::builder().build("rolling_request", Box::new(request_log)))
                    .logger(
                        Logger::builder()
                            .appender("rolling_request")
                            .additive(false)
                            .build("requests", LevelFilter::Info),
                    )
            }
            Err(e) => error!("Could not open request log {}: {}", request_log_path, e),
        }

        config_builder
            .build(root_builder.build(LevelFilter::Info))
            .unwrap()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_impl() {
        assert_eq!(
            Config::default(),
            Config {
                log_path: default_log_path(),
                control_port: default_control_port(),
                webhook_port: default_webhook_port(),
                cleanup_interval: default_cleanup_interval(),
                log_rotate_size: default_log_rotate_size(),
                log_rotate_keep: default_log_rotate_keep()
            }
        );
    }

    #[test]
    fn from_yaml() {
        assert_eq!(
            Config {
                log_path: "/var/log/webhook-installer".to_owned(),
                control_port: default_control_port(),
                webhook_port: 80,
                cleanup_interval: default_cleanup_interval(),
                log_rotate_size: 20*1024,
                log_rotate_keep: default_log_rotate_keep()
            },
            Config::from_yaml_string(
                r"
                key: value
                list:
                  - a
                  - b
                config:
                  log_rotate_size: 20480
                  webhook_port: 80
                  log_path: /var/log/webhook-installer
            ",
                "config"
            )
        );
    }
}
