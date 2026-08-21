use std::{collections::BTreeMap, time::Duration};

use mmf_platform::{
    OutboundDestinationPolicy, OutboundHttpClient, OutboundHttpMethod, OutboundHttpRequest,
    PlatformError, ReqwestOutboundHttpClient,
};
use serde::Deserialize;
use tokio::{
    io::{AsyncReadExt as _, AsyncWriteExt as _},
    net::TcpListener,
};

#[test]
fn outbound_request_contract_fails_closed_on_unsafe_or_unbounded_configuration() {
    for url in [
        "file:///tmp/secret",
        "https://user:password@example.com/private",
        "not a URL",
    ] {
        assert!(request(url, 1024).validate().is_err());
    }
    assert!(request("https://example.com", 0).validate().is_err());
    assert!(
        request("https://example.com", 64 * 1024 * 1024 + 1)
            .validate()
            .is_err()
    );
    let mut invalid_header = request("https://example.com", 1024);
    invalid_header
        .headers
        .insert("bad header".into(), "value".into());
    assert!(invalid_header.validate().is_err());
}

#[tokio::test]
async fn reqwest_provider_returns_bounded_bodies_without_following_redirects() {
    let client = ReqwestOutboundHttpClient::new(Duration::from_secs(2)).unwrap();
    let (url, task) = serve_once(
        "HTTP/1.1 302 Found\r\nLocation: https://attacker.example/\r\nContent-Length: 8\r\n\r\nredirect",
    )
    .await;
    let response = client.execute(request(&url, 1024)).await.unwrap();
    assert_eq!(response.status, 302);
    assert_eq!(response.body, b"redirect");
    task.await.unwrap();

    let (url, task) = serve_once(
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\n\r\n{\"ok\":true}",
    )
    .await;
    let response = client.execute(request(&url, 11)).await.unwrap();
    assert_eq!(response.json_object("probe").unwrap()["ok"], true);
    task.await.unwrap();

    let (url, task) = serve_once("HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n").await;
    assert!(matches!(
        client.execute(request(&url, 10)).await,
        Err(PlatformError::Operation(_))
    ));
    task.await.unwrap();
}

fn request(url: &str, maximum_response_bytes: usize) -> OutboundHttpRequest {
    OutboundHttpRequest {
        method: OutboundHttpMethod::Get,
        url: url.into(),
        headers: BTreeMap::new(),
        body: None,
        maximum_response_bytes,
    }
}

#[derive(Debug, Deserialize)]
struct DestinationContract {
    schema_version: u32,
    cases: Vec<DestinationCase>,
}

#[derive(Debug, Deserialize)]
struct DestinationCase {
    url: String,
    addresses: Vec<String>,
    #[serde(default)]
    approved_hosts: std::collections::BTreeSet<String>,
    allowed: bool,
}

#[test]
fn guarded_destination_policy_matches_the_language_neutral_contract() {
    let contract: DestinationContract = serde_json::from_str(include_str!(
        "../../../contracts/outbound-destination-security.json"
    ))
    .unwrap();
    assert_eq!(contract.schema_version, 1);
    for case in contract.cases {
        let mut policy = OutboundDestinationPolicy::public_https();
        policy.allowed_non_public_hosts = case.approved_hosts;
        let url = url::Url::parse(&case.url).unwrap();
        let addresses = case
            .addresses
            .iter()
            .map(|address| address.parse().unwrap())
            .collect::<Vec<_>>();
        assert_eq!(
            policy.validate_resolved(&url, &addresses).is_ok(),
            case.allowed,
            "{}",
            case.url
        );
    }
}

async fn serve_once(response: &'static str) -> (String, tokio::task::JoinHandle<()>) {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let task = tokio::spawn(async move {
        let (mut stream, _) = listener.accept().await.unwrap();
        let mut request = [0_u8; 2048];
        let _ = stream.read(&mut request).await.unwrap();
        stream.writable().await.unwrap();
        stream.write_all(response.as_bytes()).await.unwrap();
    });
    (format!("http://{address}/probe"), task)
}
