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

use bytes::BufMut;
use futures::{TryFutureExt, TryStreamExt};
use serde::Deserialize;
use warp::{multipart, Buf, Filter, Rejection, Reply};

use log::info;
use tokio::sync::{mpsc, oneshot};

use crate::control::{ControlMsg, ControlMsgResponse, Event, EventAuth, SessionId, SessionInit};

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
    control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    // create a response channel
    let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
    // post a new session request
    if control_channel
        .send((ControlMsg::CreateSession(data), tx))
        .await
        .is_err()
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
    control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    // create a response channel
    let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
    // post a new session request
    if control_channel
        .send((ControlMsg::RemoveSession(data), tx))
        .await
        .is_err()
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
    control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    // create a response channel
    let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
    // post a new session request
    if control_channel
        .send((ControlMsg::AddEvent(event, auth), tx))
        .await
        .is_err()
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

/// Add multiple events to session
async fn control_add_events(
    auth: EventAuth,
    events: Vec<Event>,
    control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    for event in events {
        // TODO: process results from a batch message
        control_add_event(auth.clone(), event, control_channel.clone())
            .await
            .ok();
    }
    Ok(warp::reply::with_status(
        warp::reply::json(&"Event accepted".to_owned()),
        warp::http::StatusCode::OK,
    ))
}

/// Retrieve event data
async fn control_get_logs(
    session_id: SessionId,
    range: LogQueryArgs,
    control_channel: ControlChannel,
) -> Result<impl Reply, Rejection> {
    // create a response channel
    let (tx, rx) = oneshot::channel::<ControlMsgResponse>();
    // post a new session request
    if control_channel
        .send((
            ControlMsg::GetEvents {
                session_id,
                first_entry: range.start,
                last_entry: range.end,
            },
            tx,
        ))
        .await
        .is_err()
    {
        return Ok(warp::reply::with_status(
            warp::reply::json(
                &"Session data could not be retrieved (control unavailable)".to_owned(),
            ),
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
                &"Session data could not be retrieved (no response from control)".to_owned(),
            ),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        )),
        _ => Ok(warp::reply::with_status(
            warp::reply::json(
                &"Session data could not be retrieved (wrong response from control)".to_owned(),
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
        .and(channel)
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

/// Convert text body to an Event
fn buf_to_string_event(mut body: impl Buf) -> Event {
    let mut result: String = "".to_owned();
    while body.has_remaining() {
        let cnt = body.chunk().len();
        result += &String::from_utf8_lossy(body.chunk());
        body.advance(cnt);
    }
    Event::Text(result)
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

    let log_sink = warp::post()
        .and(warp::path("log"))
        .and(webhook_auth())
        .and(warp::body::content_length_limit(1024 * 1024 * 16))
        .and(warp::body::aggregate().map(buf_to_string_event))
        .and(channel.clone())
        .and_then(control_add_event);

    let bin_sink = warp::post()
        .and(warp::path("bin"))
        .and(webhook_auth())
        .and(multipart_filter_to_events())
        .and(channel)
        .and_then(control_add_events);

    let log = warp::log("requests");
    log_sink
        .or(bin_sink)
        .recover(handle_rejection)
        .or(any)
        .with(log)
        .boxed()
}

/// OAuth-based authorization filter
///
/// This filter parses Authorization header that should be present for correct routing
/// to a webhook session
fn webhook_auth() -> impl Filter<Extract = (EventAuth,), Error = Rejection> + Copy {
    warp::header::<String>("Authorization").map(|auth: String| {
        let mut origin: &str = "";
        let mut secret: &str = "";
        for s in auth
            .split(',')
            .map(|s| s.trim_start())
            .filter(|s| s.starts_with("oauth_"))
        {
            for value in s.split('=').skip(1) {
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
    })
}

/// Request filter for multipart data type
///
/// Multipart is used when uploading files to the server.
/// This filter extracts uploaded files
fn multipart_filter_to_events() -> impl Filter<Extract = (Vec<Event>,), Error = Rejection> + Clone {
    multipart::form().and_then(|form: multipart::FormData| async {
        form.try_fold(Vec::new(), |mut events, part| async {
            // Take the part with the given name and collect associated stream
            let name = part.name().to_string();
            part.stream()
                .try_fold(Vec::new(), |mut vec, data| async {
                    vec.put(data);
                    Ok(vec)
                })
                .await
                .map(|data| {
                    events.push(Event::Raw(name, data));
                    events
                })
        })
        .map_err(|e| {
            info!("Multipart not accepted: {}", e);
            warp::reject()
        })
        .await
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    // Implement PartialEq for test convenience,
    // main code should not use direct comparisons
    impl std::cmp::PartialEq for EventAuth {
        fn eq(&self, other: &Self) -> bool {
            self.ident == other.ident && self.signature == other.signature
        }
    }

    impl std::cmp::PartialEq for Event {
        fn eq(&self, other: &Self) -> bool {
            if let Event::Text(other_text) = other {
                match self {
                    Event::Text(t) => t == other_text,
                    _ => false,
                }
            } else if let Event::Raw(other_ident, other_data) = other {
                match self {
                    Event::Raw(ident, data) => ident == other_ident && data == other_data,
                    _ => false,
                }
            } else {
                false
            }
        }
    }
    impl std::fmt::Debug for Event {
        fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
            match self {
                Event::Text(t) => f.debug_tuple("Event::Text").field(t).finish(),
                Event::Raw(ident, d) => f
                    .debug_tuple("Event::Raw")
                    .field(ident)
                    .field(&d.len())
                    .finish(),
            }
        }
    }

    #[tokio::test]
    async fn test_auth() {
        let filter = webhook_auth();
        let expected = EventAuth {
            ident: "authkey".to_owned(),
            signature: "authtoken".to_owned(),
        };

        let value = warp::test::request()
            .header(
                "Authorization",
                "oauth_signature=empty,oauth_consumer_key=authkey,\
                    oauth_broken=false,oauth_token=authtoken",
            )
            .path("/log")
            .filter(&filter)
            .await
            .unwrap();
        assert_eq!(value, expected);

        let value = warp::test::request()
            .header(
                "Authorization",
                "oauth_consumer_key=somethingelse,oauth_token=authtoken",
            )
            .path("/log")
            .filter(&filter)
            .await
            .unwrap();
        assert_ne!(value, expected);
    }

    #[tokio::test]
    async fn test_body_to_event() {
        let filter = warp::post()
            .and(warp::body::content_length_limit(1024 * 1024 * 16))
            .and(warp::body::aggregate().map(buf_to_string_event));
        let expected = Event::Text("An event message".to_owned());

        let request = warp::test::request()
            .method("POST")
            .body("An event message");
        let value = request.filter(&filter).await.unwrap();
        assert_eq!(value, expected);

        let request = warp::test::request()
            .method("POST")
            .body(b"\xff\x00\xfe\x01\xfd\x02 binary test \x80\x81\x82");
        let value = request.filter(&filter).await.unwrap();
        assert_ne!(value, expected);
    }

    #[tokio::test]
    async fn test_file_to_event() {
        let filter = warp::post().and(multipart_filter_to_events());
        let expected = Event::Raw(
            "sample".to_owned(),
            "a sample uploaded file".as_bytes().to_vec(),
        );
        assert_eq!(expected.to_string(), "binary:sample:22");
        let expected_other = Event::Raw(
            "other file".to_owned(),
            "another uploaded file".as_bytes().to_vec(),
        );

        let unexpected = Event::Raw(
            "sample".to_owned(),
            "not a sample uploaded file".as_bytes().to_vec(),
        );

        let boundary = "--abcdef1234--";
        let body = format!(
            "\
             --{0}\r\n\
             content-disposition: form-data; name=\"sample\"\r\n\r\n\
             a sample uploaded file\r\n\
             --{0}\r\n\
             content-disposition: form-data; name=\"other file\"\r\n\r\n\
             another uploaded file\r\n\
             --{0}--\r\n\
             ",
            boundary
        );

        let request = warp::test::request()
            .method("POST")
            .header("content-length", body.len())
            .header(
                "content-type",
                format!("multipart/form-data; boundary={}", boundary),
            )
            .body(body);
        let value = request.filter(&filter).await.unwrap();
        assert_eq!(value.get(0), Some(&expected));
        assert_ne!(value.get(0), Some(&unexpected));
        assert_eq!(value.get(1), Some(&expected_other));

        // test malformed multipart request
        let body = format!(
            "\
             --{0}\r\n\
             content-disposition: form-data; name=\"sample\"\r\n\r\n\
             a sample uploaded file\r\n\
             --wrong boundary--\r\n\
             ",
            boundary
        );

        let request = warp::test::request()
            .method("POST")
            .header("content-length", body.len())
            .header(
                "content-type",
                format!("multipart/form-data; boundary={}", boundary),
            )
            .body(body);
        let value = request.filter(&filter).await;
        assert!(value.is_err());
    }
}
