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
use warp::{Buf, Filter, Rejection, Reply};

use log::info;
use tokio::sync::{mpsc, oneshot};

use crate::lib::{ControlMsg, ControlMsgResponse, Event, EventAuth, SessionId, SessionInit};

pub type ControlChannel = mpsc::Sender<(ControlMsg, oneshot::Sender<ControlMsgResponse>)>;

/// Query arguments for retrieving a slice of events
#[derive(Deserialize)]
struct LogQueryArgs {
    start: usize,
    end: usize,
}

/// Handle CreateSession command
async fn control_create_session(
    data: SessionInit,
    mut control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    // create a response channel
    let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
    // post a new session request
    if let Err(_) = control_channel
        .send((ControlMsg::CreateSession(data), tx))
        .await
    {
        return Ok(warp::reply::with_status(
            warp::reply::json(&"Session could not be started (control unavailable)".to_owned()),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        ));
    }
    // wait for reply
    match rx.await {
        Ok(ControlMsgResponse::Success) => Ok(warp::reply::with_status(
            warp::reply::json(&"Session accepted".to_owned()),
            warp::http::StatusCode::CREATED,
        )),
        Ok(ControlMsgResponse::Failure) => Ok(warp::reply::with_status(
            warp::reply::json(&"Session could not be started".to_owned()),
            warp::http::StatusCode::BAD_REQUEST,
        )),
        Err(_) => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Session could not be started (no response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
        _ => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Session could not be started (wrong response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
    }
}

/// Handle RemoveSession command
async fn control_remove_session(
    data: SessionId,
    mut control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    // create a response channel
    let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
    // post a new session request
    if let Err(_) = control_channel
        .send((ControlMsg::RemoveSession(data), tx))
        .await
    {
        return Ok(warp::reply::with_status(
            warp::reply::json(&"Session could not be removed (control unavailable)".to_owned()),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        ));
    }

    // wait for reply
    match rx.await {
        Ok(ControlMsgResponse::Success) => Ok(warp::reply::with_status(
            warp::reply::json(&"Session removed".to_owned()),
            warp::http::StatusCode::OK,
        )),
        Ok(ControlMsgResponse::Failure) => Ok(warp::reply::with_status(
            warp::reply::json(&"Session not found".to_owned()),
            warp::http::StatusCode::NOT_FOUND,
        )),
        Err(_) => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Session could not be removed (no response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
        _ => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Session could not be started (wrong response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
    }
}

/// Add event to session
async fn control_add_event(
    auth: EventAuth,
    event: Event,
    mut control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    // create a response channel
    let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
    // post a new session request
    if let Err(_) = control_channel
        .send((ControlMsg::AddEvent(event, auth), tx))
        .await
    {
        return Ok(warp::reply::with_status(
            warp::reply::json(&"Event could not be added (control unavailable)".to_owned()),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        ));
    }
    // wait for reply
    match rx.await {
        Ok(ControlMsgResponse::Success) => Ok(warp::reply::with_status(
            warp::reply::json(&"Event accepted".to_owned()),
            warp::http::StatusCode::OK,
        )),
        Ok(ControlMsgResponse::Failure) => Ok(warp::reply::with_status(
            warp::reply::json(&"Event was not accepted".to_owned()),
            warp::http::StatusCode::BAD_REQUEST,
        )),
        Err(_) => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Event could not be delivered (no response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
        _ => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Event could not be delivered (wrong response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
    }
}

/// Retrieve event data
async fn control_get_logs(
    session_id: SessionId,
    range: LogQueryArgs,
    mut control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    // create a response channel
    let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
    // post a new session request
    if let Err(_) = control_channel
        .send((
            ControlMsg::GetEvents {
                session_id,
                first_entry: range.start,
                last_entry: range.end,
            },
            tx,
        ))
        .await
    {
        return Ok(warp::reply::with_status(
            warp::reply::json(&"Session could not be removed (control unavailable)".to_owned()),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        ));
    }
    //control.add_session(Session::new(data.id, &data.log_path, data.timeout, &data.secret));
    // wait for reply
    match rx.await {
        Ok(ControlMsgResponse::EventsData(log)) => Ok(warp::reply::with_status(
            warp::reply::json(&log),
            warp::http::StatusCode::OK,
        )),
        Ok(ControlMsgResponse::Failure) => Ok(warp::reply::with_status(
            warp::reply::json(&"Session not found".to_owned()),
            warp::http::StatusCode::NOT_FOUND,
        )),
        Err(_) => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Session could not be removed (no response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
        _ => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Session could not be started (wrong response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
    }
}

/// Create Control server routes
pub fn create_control_server(
    control_channel: ControlChannel,
) -> warp::filters::BoxedFilter<(impl Reply,)> {
    let any = warp::any()
        .and(warp::path::full())
        .map(|full: warp::path::FullPath| {
            info!("Unhandled control route {}", full.as_str());
            warp::reply()
        })
        .map(|reply| warp::reply::with_status(reply, warp::http::StatusCode::NOT_FOUND));

    // create a warp filter, which will inject control_channel into callback argument list
    let channel = warp::any().map(move || control_channel.clone());

    let new_sess = warp::post()
        .and(warp::path("session"))
        .and(warp::body::json())
        .and(channel.clone())
        .and_then(control_create_session);

    let del_sess = warp::delete()
        .and(warp::path!("session" / SessionId))
        .and(channel.clone())
        .and_then(control_remove_session);

    let get_logs = warp::get()
        .and(warp::path!("session" / SessionId / "logs"))
        .and(warp::query::<LogQueryArgs>())
        .and(channel.clone())
        .and_then(control_get_logs);

    let log = warp::log("requests");
    new_sess.or(del_sess).or(get_logs).or(any).with(log).boxed()
}

async fn handle_rejection(err: Rejection) -> Result<impl Reply, Rejection> {
    error!("Unhandled rejection: {:?}", err);
    Ok(warp::reply::with_status(
        "Request declined",
        warp::http::StatusCode::BAD_REQUEST,
    ))
}

fn buf_to_event(mut body: impl Buf) -> Event {
    let mut result: Event = "".to_owned();
    while body.has_remaining() {
        let cnt = body.bytes().len();
        result += &String::from_utf8_lossy(body.bytes());
        body.advance(cnt);
    }
    result
}

/// Create webhook server routes
///
/// Webhook listens to log events from an installer
/// and passes log data to controller for processing
pub fn create_webhook_server(
    control_channel: ControlChannel,
) -> warp::filters::BoxedFilter<(impl Reply,)> {
    let any = warp::any()
        .and(warp::path::full())
        .map(|full: warp::path::FullPath| {
            info!("Unhandled webhook route {}", full.as_str());
            warp::reply()
        })
        .map(|reply| warp::reply::with_status(reply, warp::http::StatusCode::NOT_FOUND));

    // create a warp filter, which will inject control_channel into callback argument list
    let channel = warp::any().map(move || control_channel.clone());

    let sink = warp::post()
        .and(warp::path("log"))
        .and(warp::header::<String>("Authorization").map(|auth: String| {
            let mut origin: &str = "";
            let mut secret: &str = "";
            for s in auth
                .split(",")
                .map(|s| s.trim_start())
                .filter(|s| s.starts_with("oauth_"))
            {
                for value in s.split("=").skip(1) {
                    if s.starts_with("oauth_consumer_key") {
                        origin = value.trim_matches('"');
                    } else if s.starts_with("oauth_token") {
                        secret = value.trim_matches('"');
                    }
                }
            }
            EventAuth {
                ident: origin.to_owned(),
                signature: secret.to_owned(),
            }
        }))
        .and(warp::body::content_length_limit(1024 * 1024 * 16))
        .and(warp::body::aggregate().map(buf_to_event))
        .and(channel)
        .and_then(control_add_event);

    let log = warp::log("requests");
    sink.recover(handle_rejection).or(any).with(log).boxed()
}
