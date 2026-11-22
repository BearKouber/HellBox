//! Shared installer and dispatcher contract; no dependency on either application.
pub mod boot;
pub mod discover;
pub mod install;
pub mod transport;
pub mod win;
pub const HOST_SOURCE: &str = include_str!("../lua/host.lua");
