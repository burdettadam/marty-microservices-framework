//! Explicit compatibility with the frozen `CPython` 3.12 configuration grammar.
//!
//! These opt-in parsers do not change MMF's existing JSON/TOML scalar handling.
//! Integer parsing preserves exact decimal values (up to the observed 4300-digit
//! policy); SQL/time limits belong at the consumer boundary, not at startup.
//! There is no Python runtime dependency or floating-point integer conversion.

use std::{cmp::Ordering, fmt, str::FromStr};

/// Selected deployed runtime's decimal integer conversion policy.
pub const PYTHON_CONFIG_INTEGER_DIGIT_LIMIT: usize = 4_300;

/// A numeric grammar failure; never includes the original configuration value.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidConfigNumber;

impl fmt::Display for InvalidConfigNumber {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("invalid numeric configuration")
    }
}

impl std::error::Error for InvalidConfigNumber {}

/// Canonical signed decimal storage for lossless configuration integers.
///
/// No arithmetic or machine width is imposed during parsing. Use ordinary
/// `min`/`max` for domain bounds, then explicitly check conversion at the actual
/// consumer. The representation is private so invalid strings cannot be built.
///
/// ```
/// use mmf_config::numeric_config::{InvalidConfigNumber, PythonConfigInteger};
/// let limit: PythonConfigInteger = "18446744073709551616".parse()?;
/// assert_eq!(limit.to_i64(), None); // Startup accepts the exact value.
/// let oauth_limit = limit.min(500_u64.into()); // Domain cap before SQL binding.
/// assert_eq!(oauth_limit.to_i64(), Some(500));
/// # Ok::<(), InvalidConfigNumber>(())
/// ```
#[derive(Clone, Eq, Hash, PartialEq)]
pub struct PythonConfigInteger(Box<str>);

impl PythonConfigInteger {
    #[must_use]
    pub fn as_decimal(&self) -> &str {
        &self.0
    }

    /// Checked conversion; an out-of-range value stays intact in this object.
    #[must_use]
    pub fn to_i64(&self) -> Option<i64> {
        self.0.parse().ok()
    }

    #[must_use]
    pub fn to_u64(&self) -> Option<u64> {
        self.0.parse().ok()
    }

    #[must_use]
    pub fn to_usize(&self) -> Option<usize> {
        self.0.parse().ok()
    }

    fn sign_and_magnitude(&self) -> (bool, &str) {
        self.0
            .strip_prefix('-')
            .map_or((false, self.0.as_ref()), |magnitude| (true, magnitude))
    }
}

impl FromStr for PythonConfigInteger {
    type Err = InvalidConfigNumber;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let normalized = normalize_numeric(value)?;
        let (negative, digits) = if let Some(digits) = normalized.strip_prefix('-') {
            (true, digits)
        } else {
            (false, normalized.strip_prefix('+').unwrap_or(&normalized))
        };
        if digits.is_empty()
            || digits.len() > PYTHON_CONFIG_INTEGER_DIGIT_LIMIT
            || !digits.bytes().all(|byte| byte.is_ascii_digit())
        {
            return Err(InvalidConfigNumber);
        }
        // The runtime counts leading zeroes before canonicalizing, but not
        // valid digit separators. Negative zero has a single canonical form.
        let magnitude = digits.trim_start_matches('0');
        let canonical = if magnitude.is_empty() {
            "0".to_owned()
        } else if negative {
            format!("-{magnitude}")
        } else {
            magnitude.to_owned()
        };
        Ok(Self(canonical.into_boxed_str()))
    }
}

impl From<u64> for PythonConfigInteger {
    fn from(value: u64) -> Self {
        Self(value.to_string().into_boxed_str())
    }
}

impl From<i64> for PythonConfigInteger {
    fn from(value: i64) -> Self {
        Self(value.to_string().into_boxed_str())
    }
}

impl Ord for PythonConfigInteger {
    fn cmp(&self, other: &Self) -> Ordering {
        let (left_negative, left) = self.sign_and_magnitude();
        let (right_negative, right) = other.sign_and_magnitude();
        match (left_negative, right_negative) {
            (true, false) => Ordering::Less,
            (false, true) => Ordering::Greater,
            _ => {
                let magnitude = left.len().cmp(&right.len()).then_with(|| left.cmp(right));
                if left_negative {
                    magnitude.reverse()
                } else {
                    magnitude
                }
            }
        }
    }
}

impl PartialOrd for PythonConfigInteger {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl fmt::Display for PythonConfigInteger {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.0)
    }
}

impl fmt::Debug for PythonConfigInteger {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self, formatter)
    }
}

/// Parse the frozen Python float grammar, including non-finite values.
///
/// Use [`parse_bounded_python_config_float`] for the ordered
/// `max(low, min(high, value))` behavior. Do not call `clamp` and then construct
/// a `Duration` from NaN, or reject it before applying the observed domain bounds.
pub fn parse_python_config_float(value: &str) -> Result<f64, InvalidConfigNumber> {
    normalize_numeric(value)?
        .parse()
        .map_err(|_| InvalidConfigNumber)
}

/// Parse and apply finite domain bounds in Python's exact comparison order.
///
/// NaN selects the high bound; infinities select their respective bound. Equal
/// values select the bound operand, including its signed-zero representation.
/// Invalid bounds are rejected; accepted results are finite and bounded.
pub fn parse_bounded_python_config_float(
    value: &str,
    minimum: f64,
    maximum: f64,
) -> Result<f64, InvalidConfigNumber> {
    if !minimum.is_finite() || !maximum.is_finite() || minimum > maximum {
        return Err(InvalidConfigNumber);
    }
    let parsed = parse_python_config_float(value)?;
    // Explicit ordered comparisons matter: clamp preserves NaN, and floating
    // min/max need not choose Python's bound operand for equal signed zeroes.
    let upper_bounded = if parsed < maximum { parsed } else { maximum };
    Ok(if upper_bounded > minimum {
        upper_bounded
    } else {
        minimum
    })
}

fn normalize_numeric(value: &str) -> Result<String, InvalidConfigNumber> {
    let trimmed =
        value.trim_matches(|character| NUMERIC_WHITESPACE.contains(&u32::from(character)));
    let mut normalized = String::with_capacity(trimmed.len());
    for character in trimmed.chars() {
        if character.is_ascii() {
            normalized.push(character);
        } else if let Some(digit) = decimal_digit(character) {
            normalized.push(char::from(b'0' + digit));
        } else {
            return Err(InvalidConfigNumber);
        }
    }
    // Python permits separators ONLY between decimal digits, including exponent
    // digits. Reject malformed placement before removing any separator.
    let bytes = normalized.as_bytes();
    for (index, byte) in bytes.iter().enumerate() {
        if *byte == b'_'
            && (index == 0
                || index + 1 == bytes.len()
                || !bytes[index - 1].is_ascii_digit()
                || !bytes[index + 1].is_ascii_digit())
        {
            return Err(InvalidConfigNumber);
        }
    }
    normalized.retain(|character| character != '_');
    Ok(normalized)
}

fn decimal_digit(character: char) -> Option<u8> {
    let codepoint = u32::from(character);
    let index = DECIMAL_ZERO_CODEPOINTS.partition_point(|start| *start <= codepoint);
    let start = DECIMAL_ZERO_CODEPOINTS.get(index.checked_sub(1)?)?;
    let digit = codepoint - start;
    (digit < 10).then(|| u8::try_from(digit).expect("decimal digit is below ten"))
}

// Observed in the pinned CPython 3.12.13 runtime (Unicode 15.0.0).
// Each zero begins exactly ten consecutive Nd codepoints; see the exhaustive
// language-neutral oracle and numeric_config tests. Do not use is_numeric():
// Roman numerals and superscripts are not Python decimal digits.
const DECIMAL_ZERO_CODEPOINTS: &[u32] = &[
    0x30, 0x660, 0x6F0, 0x7C0, 0x966, 0x9E6, 0xA66, 0xAE6, 0xB66, 0xBE6, 0xC66, 0xCE6, 0xD66,
    0xDE6, 0xE50, 0xED0, 0xF20, 0x1040, 0x1090, 0x17E0, 0x1810, 0x1946, 0x19D0, 0x1A80, 0x1A90,
    0x1B50, 0x1BB0, 0x1C40, 0x1C50, 0xA620, 0xA8D0, 0xA900, 0xA9D0, 0xA9F0, 0xAA50, 0xABF0, 0xFF10,
    0x104A0, 0x10D30, 0x11066, 0x110F0, 0x11136, 0x111D0, 0x112F0, 0x11450, 0x114D0, 0x11650,
    0x116C0, 0x11730, 0x118E0, 0x11950, 0x11C50, 0x11D50, 0x11DA0, 0x11F50, 0x16A60, 0x16AC0,
    0x16B50, 0x1D7CE, 0x1D7D8, 0x1D7E2, 0x1D7EC, 0x1D7F6, 0x1E140, 0x1E2F0, 0x1E4F0, 0x1E950,
    0x1FBF0,
];
const NUMERIC_WHITESPACE: &[u32] = &[
    0x9, 0xA, 0xB, 0xC, 0xD, 0x20, 0x85, 0xA0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004,
    0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000,
];
