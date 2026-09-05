//! Shared wildcard matching for message and gateway routing.

/// Match an entire value using `*` for zero or more characters and `?` for one.
///
/// Matching is case-sensitive and operates on Unicode scalar values. Separators
/// such as `/` and `.` are ordinary characters; wildcards can match across them.
/// There is no escape syntax or special treatment of repeated stars.
#[must_use]
pub fn wildcard_matches(pattern: &str, value: &str) -> bool {
    let pattern: Vec<char> = pattern.chars().collect();
    let value: Vec<char> = value.chars().collect();
    let (mut pattern_index, mut value_index, mut star, mut retry) = (0, 0, None, 0);
    while value_index < value.len() {
        if pattern_index < pattern.len()
            && (pattern[pattern_index] == '?' || pattern[pattern_index] == value[value_index])
        {
            pattern_index += 1;
            value_index += 1;
        } else if pattern_index < pattern.len() && pattern[pattern_index] == '*' {
            star = Some(pattern_index);
            retry = value_index;
            pattern_index += 1;
        } else if let Some(star_index) = star {
            pattern_index = star_index + 1;
            retry += 1;
            value_index = retry;
        } else {
            return false;
        }
    }
    while pattern_index < pattern.len() && pattern[pattern_index] == '*' {
        pattern_index += 1;
    }
    pattern_index == pattern.len()
}
