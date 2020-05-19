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

#[macro_use]
extern crate log;
use tokio::signal::unix::{signal, Signal, SignalKind};
use tokio::sync::{mpsc, oneshot};

mod config;
mod lib;
mod servers;
use crate::config::Config;
use crate::lib::{Control, ControlMsg, ControlMsgResponse};
use crate::servers::{create_control_server, create_webhook_server};

fn get_config_location() -> String {
    std::env::var("TESSIA_CFG").unwrap_or("/etc/tessia/server.yaml".to_owned())
}

#[tokio::main]
async fn main() {
    // Start with log to console to check for configuration issues
    let log_handle = log4rs::init_config(Config::get_safe_looger_config()).unwrap();
    // Load configuration
    let cfg = Config::from_yaml_file(&get_config_location(), "installer-webhook");
    // Switch to normal log
    log_handle.set_config(cfg.get_logger_config());

    let mut control = Control::new();
    let (control_tx, mut control_rx) =
        mpsc::channel::<(ControlMsg, oneshot::Sender<ControlMsgResponse>)>(100);

    let (control_shutdown_tx, control_shutdown_rx) = oneshot::channel::<()>();
    let (webhook_shutdown_tx, webhook_shutdown_rx) = oneshot::channel::<()>();

    // Control task, owns all sessions and processes messages from servers
    let control_task = {
        tokio::spawn(async move {
            info!("Started control task");
            // listen to messages on rx
            while let Some((msg, res_channel)) = control_rx.recv().await {
                // msg_type for logging purposes
                let msg_type = msg.get_type();
                // handle message; may return Err on shutdown
                let result = control.handle_message(msg);
                match result {
                    Ok(ok) => {
                        if let Err(_) = res_channel.send(ok) {
                            info!(
                                "Message {} handled, but response could not be sent",
                                msg_type
                            );
                        }
                    }
                    Err(_) => break,
                }
            }
            info!("Shutting down");
            vec![control_shutdown_tx, webhook_shutdown_tx]
                .into_iter()
                .map(|tx| tx.send(()))
                .for_each(drop);
        })
    };

    // Launch control server
    let control_server_task = {
        let port = cfg.control_port;
        let control_tx = control_tx.clone();
        let (_, server) = warp::serve(create_control_server(control_tx))
            .bind_with_graceful_shutdown(([127, 0, 0, 1], port), async {
                control_shutdown_rx.await.ok();
            });
        info!("Starting control on port {}", port);
        tokio::spawn(server)
    };

    // Launch webhook server
    let webhook_server_task = {
        let port = cfg.webhook_port;
        let control_tx = control_tx.clone();
        let (_, server) = warp::serve(create_webhook_server(control_tx))
            .bind_with_graceful_shutdown(([0, 0, 0, 0], port), async {
                webhook_shutdown_rx.await.ok();
            });
        info!("Starting webhook on port {}", port);
        tokio::spawn(server)
    };

    // Listen for SIGTERM from outside
    let circuit_breaker = {
        let mut control_tx = control_tx.clone();
        tokio::spawn(async move {
            let mut term_stream: Signal = signal(SignalKind::terminate()).unwrap();
            term_stream.recv().await;
            info!("Caught SIGTERM, terminating...");
            let (tx, _) = oneshot::channel::<ControlMsgResponse>();
            control_tx.send((ControlMsg::Shutdown, tx)).await.ok();
        })
    };

    // Periodically schedule cleanup tasks on control
    {
        let mut control_tx = control_tx.clone();
        let cleanup_interval = std::time::Duration::from_secs(cfg.cleanup_interval.into());
        info!(
            "Cleanup interval set for {} seconds",
            cleanup_interval.as_secs()
        );
        tokio::spawn(async move {
            let mut timer = tokio::time::interval(cleanup_interval);
            loop {
                timer.tick().await;
                let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
                control_tx.send((ControlMsg::Cleanup, tx)).await.ok();
                rx.await.map(|_| info!("Cleanup cycle completed")).ok();
            }
        })
    };

    let res = tokio::try_join!(
        control_server_task,
        webhook_server_task,
        control_task,
        circuit_breaker
    );
    match res {
        Ok(_) => {
            info!("Graceful exit");
        }
        Err(e) => {
            error!("Emergency exit {:?}", e);
        }
    }
}
