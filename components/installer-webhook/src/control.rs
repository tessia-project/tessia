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
use std::io::Write;

use log::{info, warn};
use std::collections::{BTreeMap, HashMap};

enum TriState<T> {
    Yes(T),
    Maybe,
    Never,
}

pub type SessionId = String;
pub enum Event {
    Text(String),
    Raw(String, Vec<u8>), // ident, data
}

/// Text representation for Event
///
/// Text events are represented as themselves,
/// raw only indicate name and length
impl std::fmt::Display for Event {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            Event::Text(t) => write!(f, "{}", t),
            Event::Raw(ident, d) => write!(f, "binary:{}:{}", ident, d.len()),
        }
    }
}

/// Installation session
///
/// A session in Control structure allows accepting requests, posted
/// to this webhook.
struct Session {
    pub id: SessionId,
    log_path: String,
    timeout: u32,

    /// secret can be used to verify authenticity of the sender
    secret: String,

    log: BTreeMap<usize, Event>,
    file_descriptor: TriState<std::fs::File>,
    last_updated: std::time::Instant,
}

/// Information required to start a session
#[derive(Deserialize, Debug)]
pub struct SessionInit {
    pub id: SessionId,
    pub log_path: String,
    pub timeout: u32,
    pub secret: String,
}

/// A single installation session
///
/// Accumulates events for the installation
impl Session {
    pub fn new(init: SessionInit) -> Self {
        Session {
            id: init.id,
            log_path: init.log_path,
            timeout: init.timeout,
            secret: init.secret,
            log: BTreeMap::<usize, Event>::new(),
            file_descriptor: TriState::Maybe,
            last_updated: std::time::Instant::now(),
        }
    }

    /// Add an event
    fn add_log_entry(&mut self, event: Event) {
        let key = self.log.len();
        self.log.insert(key, event);
        self.last_updated = std::time::Instant::now();

        // resolve a maybe situation
        if let TriState::Maybe = self.file_descriptor {
            self.file_descriptor = std::fs::File::create(self.log_path.clone() + "/events.log")
                .map(TriState::Yes)
                .unwrap_or(TriState::Never);
        }

        // write the result
        if let Some(ev) = self.log.get(&key) {
            match ev {
                Event::Text(text) => {
                    if let TriState::Yes(ref mut fd) = self.file_descriptor {
                        // consume any write errors, we're not safe if disk space ended anyway
                        writeln!(fd, "{}", text).ok();
                    }
                }
                Event::Raw(ident, data) => {
                    let filename = safe_filename(ident);
                    if let Ok(mut fd) =
                        std::fs::File::create(format!("{}/{}", self.log_path.clone(), filename))
                    {
                        // consume any write errors, we're not safe if disk space ended anyway
                        fd.write(data).ok();
                    }
                }
            }
        }
    }

    /// Retrieve a range of events
    fn get_log_entries(&self, start: usize, end: Option<usize>) -> Vec<String> {
        let iter = match end {
            Some(_end) => self.log.range(start.._end),
            None => self.log.range(start..),
        };
        iter.map(|(_, v)| v.to_string()).collect()
    }
}

/// Event authorization data
///
/// Every event should provide some credentials in order to be
/// successfully processed.
#[derive(Debug, Clone)]
pub struct EventAuth {
    pub ident: String,
    pub signature: String,
}
impl EventAuth {
    /// Verify signature of the incoming event
    fn verify(&self, secret: &str) -> bool {
        self.signature.trim() == secret.trim()
    }
}

/// Session control
///
/// Starts and stops processing logs with specific authoriation data
pub struct Control {
    sessions: HashMap<SessionId, Session>,
}

/// Messages passed to control
// #[derive(Debug)]
pub enum ControlMsg {
    CreateSession(SessionInit),
    RemoveSession(SessionId),
    AddEvent(Event, EventAuth),
    GetEvents {
        session_id: SessionId,
        first_entry: usize,
        last_entry: usize,
    },
    Cleanup,
    Shutdown,
}
impl ControlMsg {
    pub fn get_type(&self) -> &'static str {
        match self {
            Self::CreateSession(_) => "CreateSession",
            Self::RemoveSession(_) => "RemoveSession",
            Self::AddEvent(_, _) => "AddEvent",
            Self::GetEvents {
                session_id: _,
                first_entry: _,
                last_entry: _,
            } => "GetEvents",
            Self::Cleanup => "Cleanup",
            Self::Shutdown => "Shutdown",
        }
    }
}

/// Responses from control
#[derive(Debug)]
pub enum ControlMsgResponse {
    Success,
    Failure,
    EventsData(Vec<String>),
}

impl Control {
    /// Initialize control struct
    pub fn new() -> Self {
        Control {
            sessions: HashMap::<SessionId, Session>::new(),
        }
    }

    /// Attempt to add a new session
    ///
    /// Returns true on success
    fn add_session(&mut self, session: Session) -> bool {
        let id = session.id.clone();
        if self.sessions.insert(id.clone(), session).is_none() {
            info!("New session {}", id);
        } else {
            info!("Replacing session {}", id);
        }
        true
    }

    /// Attempt to rmove a new session
    ///
    /// Returns true on success
    fn remove_session(&mut self, session_id: SessionId) -> bool {
        self.sessions.remove(&session_id).is_some() && {
            info!("Removed session {}", session_id);
            true
        }
    }

    /// Process incoming log event
    fn process_event(&mut self, evt: Event, auth: EventAuth) -> Result<(), String> {
        if let Some(session) = self.sessions.get_mut(&auth.ident) {
            if !auth.verify(&session.secret) {
                warn!("Invalid authorization signature {:?}", auth);
                return Err("Invalid authorization token".to_owned());
            }
            session.add_log_entry(evt);
        } else {
            warn!("Expired on non-existing authorization ident {:?}", auth);
            return Err("Session ident expired or non-existing".to_owned());
        }
        Ok(())
    }

    /// Get list of events
    fn get_event_list(
        &self,
        session_id: SessionId,
        first_entry: usize,
        last_entry: usize,
    ) -> Result<Vec<String>, String> {
        if let Some(session) = self.sessions.get(&session_id) {
            if last_entry == 0 {
                Ok(session.get_log_entries(first_entry, None))
            } else {
                Ok(session.get_log_entries(first_entry, Some(last_entry)))
            }
        } else {
            Err("Session ident expired or non-existing".to_owned())
        }
    }

    /// Cleanup sessions that were not updated for the indicated timeout
    fn cleanup(&mut self, at_time: Option<std::time::Instant>) -> usize {
        let now = match at_time {
            Some(time) => time,
            None => std::time::Instant::now(),
        };
        let size_before = self.sessions.len();
        self.sessions.retain(|_key, val| {
            let duration = now.saturating_duration_since(val.last_updated);
            duration.as_secs() < val.timeout.into()
        });
        size_before - self.sessions.len()
    }

    /// Handle control message
    pub fn handle_message(&mut self, message: ControlMsg) -> Result<ControlMsgResponse, ()> {
        match message {
            ControlMsg::CreateSession(init_data) => {
                let session = Session::new(init_data);
                match self.add_session(session) {
                    true => Ok(ControlMsgResponse::Success),
                    false => Ok(ControlMsgResponse::Failure),
                }
            }
            ControlMsg::RemoveSession(id) => match self.remove_session(id) {
                true => Ok(ControlMsgResponse::Success),
                false => Ok(ControlMsgResponse::Failure),
            },
            ControlMsg::AddEvent(event, auth) => match self.process_event(event, auth) {
                Ok(_) => Ok(ControlMsgResponse::Success),
                Err(_) => Ok(ControlMsgResponse::Failure),
            },
            ControlMsg::GetEvents {
                session_id,
                first_entry,
                last_entry,
            } => match self.get_event_list(session_id, first_entry, last_entry) {
                Ok(vec) => Ok(ControlMsgResponse::EventsData(vec)),
                Err(_) => Ok(ControlMsgResponse::Failure),
            },
            ControlMsg::Cleanup => {
                let n_cleaned = self.cleanup(None);
                info!("Cleaned up {} sessions", n_cleaned);
                Ok(ControlMsgResponse::Success)
            }
            ControlMsg::Shutdown => Err(()),
        }
    }
}

/// Generate a filename that is safe to use in log directory
fn safe_filename(ident: &str) -> String {
    if let Some(trail) = ident.rsplit('/').next() {
        if !trail.is_empty() {
            return format!("file_{}", trail);
        }
    }

    "file_binary".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_event(timestamp: f64) -> Event {
        Event::Text(format!("event, origin, {}", timestamp))
    }

    fn make_raw_event(ident: String) -> Event {
        Event::Raw(
            ident,
            b"\xff\x00\xfe\x01\xfd\x02 binary event \x80\x81\x82".to_vec(),
        )
    }

    fn make_session(id: SessionId) -> Session {
        Session::new(SessionInit {
            id,
            log_path: "log_path".to_owned(),
            timeout: 10,
            secret: "secret".to_owned(),
        })
    }
    #[test]
    fn session_logger() {
        let mut s = make_session("1".to_owned());
        s.add_log_entry(make_event(2.4));
        s.add_log_entry(make_event(3.6));
        assert_eq!(s.get_log_entries(0, None).len(), 2);
        assert_eq!(s.get_log_entries(0, Some(1)).len(), 1);
        assert_eq!(s.get_log_entries(1, None).len(), 1);
        assert_eq!(s.get_log_entries(2, None).len(), 0);
        s.add_log_entry(make_raw_event("dump".to_owned()));
        assert_eq!(s.get_log_entries(2, None).len(), 1);
    }

    #[test]
    fn event_auth_verify() {
        let auth = EventAuth {
            ident: "id".to_owned(),
            signature: "something".to_owned(),
        };
        assert!(auth.verify("something"));
        assert!(!auth.verify("somethingelse"));
    }
    #[test]
    fn control_process_event() {
        let mut control = Control::new();
        control.add_session(make_session("1".to_owned()));

        // ok
        let auth = EventAuth {
            ident: "1".to_owned(),
            signature: "secret".to_owned(),
        };
        let e = make_event(2.4);
        assert_eq!(control.process_event(e, auth), Ok(()));

        // fail wrong secret
        let auth = EventAuth {
            ident: "404".to_owned(),
            signature: "something".to_owned(),
        };
        let e = make_event(6.5);
        assert_ne!(control.process_event(e, auth), Ok(()));
    }
    #[test]
    fn control_cleanup() {
        // check cleanup
        use std::time::{Duration, Instant};
        let mut control = Control::new();
        let now = Instant::now();

        // Create three sessions and start cleaning up
        let mut s = make_session("1".to_owned());
        s.last_updated = now;
        assert_eq!(s.timeout, 10); // our expectation for default sessions in this test: timeout = 10 seconds
        control.add_session(s);

        let mut s = make_session("2".to_owned());
        s.last_updated = now.checked_sub(Duration::from_secs(5)).unwrap();
        control.add_session(s);

        let mut s = make_session("3".to_owned());
        s.last_updated = now.checked_sub(Duration::from_secs(15)).unwrap();
        control.add_session(s);

        assert_eq!(
            control.cleanup(now.checked_sub(Duration::from_secs(120))),
            0
        ); // does not panic on time in past
        assert_eq!(control.sessions.len(), 3);
        assert_eq!(control.cleanup(None), 1); // remove last one
        assert_eq!(control.sessions.len(), 2);
        assert_eq!(control.cleanup(now.checked_add(Duration::from_secs(3))), 0); // keep second; only 8 seconds passed
        assert_eq!(control.sessions.len(), 2);
        assert_eq!(control.cleanup(now.checked_add(Duration::from_secs(7))), 1); // remove second
        assert_eq!(control.sessions.len(), 1);
        assert_eq!(
            control.cleanup(now.checked_add(Duration::from_secs(120))),
            1
        ); // remove first
        assert_eq!(control.sessions.len(), 0);
    }

    #[test]
    fn filenames() {
        assert_eq!(safe_filename("message-log.txt"), "file_message-log.txt");
        assert_eq!(safe_filename("/any/dir/"), "file_binary");
        assert_eq!(safe_filename("./.."), "file_..");
        assert_eq!(safe_filename(".."), "file_..");
        assert_eq!(safe_filename("../../../etc/passwd"), "file_passwd");
        assert_eq!(
            safe_filename("/var/log/messages.tar.gz"),
            "file_messages.tar.gz"
        );
    }
}
