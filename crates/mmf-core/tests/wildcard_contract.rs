use mmf_core::wildcard_matches;

#[test]
fn shared_routing_wildcards_preserve_character_semantics() {
    for (pattern, value, expected) in [
        ("", "", true),
        ("", "a", false),
        ("*", "", true),
        ("?", "", false),
        ("?", "é", true),
        ("?", "ab", false),
        ("orders.*", "orders.created", true),
        ("orders.*", "orders.created.extra", true),
        ("/api/*", "/api/a/b", true),
        ("a**b", "ab", true),
        ("a*b?c", "axbybzc", true),
        ("a*b", "abc", false),
        ("Orders.*", "orders.created", false),
        (r"\*", "*", false),
        (r"\*", r"\anything", true),
    ] {
        assert_eq!(
            wildcard_matches(pattern, value),
            expected,
            "{pattern:?}, {value:?}"
        );
    }
}
