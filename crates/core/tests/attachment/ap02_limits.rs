//! AP2 Provider limits only. 10 MiB per image and 25 MiB per file, except a
//! file whose extension CloudRoom types as `image/*`, which gets the image
//! limit (F26). No count cap.

use openwiz_core::attachment::{FILE_MAX_BYTES, FailReason, IMAGE_MAX_BYTES, Kind, check, limit};

use crate::support::*;

#[test]
fn ap02_limits_affected_contracts_preserve_original_cases() {
    let cases: [(&str, fn()); 5] = [
        (
            "a_file_at_25_mib_is_accepted_and_one_byte_over_is_refused",
            a_file_at_25_mib_is_accepted_and_one_byte_over_is_refused,
        ),
        (
            "a_file_cloudroom_types_as_an_image_gets_the_image_limit",
            a_file_cloudroom_types_as_an_image_gets_the_image_limit,
        ),
        (
            "an_image_at_10_mib_is_accepted_and_one_byte_over_is_refused",
            an_image_at_10_mib_is_accepted_and_one_byte_over_is_refused,
        ),
        ("the_limits_are_cloudrooms", the_limits_are_cloudrooms),
        ("there_is_no_count_cap", there_is_no_count_cap),
    ];
    for (name, proof) in cases {
        eprintln!("TA2 case: ap02_limits::{name}");
        proof();
    }
}

fn the_limits_are_cloudrooms() {
    assert_eq!(IMAGE_MAX_BYTES, 10 * MIB, "F7: 10 MiB per image");
    assert_eq!(FILE_MAX_BYTES, 25 * MIB, "F7: 25 MiB per file");
    assert_eq!(
        FailReason::ImageTooLarge.message(),
        "CloudRoom accepts images up to 10 MiB"
    );
    assert_eq!(
        FailReason::FileTooLarge.message(),
        "CloudRoom accepts files up to 25 MiB"
    );
}

fn an_image_at_10_mib_is_accepted_and_one_byte_over_is_refused() {
    for (file, magic) in [
        ("synthetic.png", PNG),
        ("synthetic.jpg", JPEG),
        ("synthetic.gif", GIF89),
        ("synthetic.webp", WEBP),
    ] {
        let at = padded(magic, IMAGE_MAX_BYTES);
        let over = padded(magic, IMAGE_MAX_BYTES + 1);
        assert_eq!(at.len() as u64, 10 * MIB);
        let n = name(file);
        assert_eq!(check(&n, &at, at.len() as u64), Ok(Kind::Image), "{file}");
        assert_eq!(
            check(&n, &over, over.len() as u64),
            Err(FailReason::ImageTooLarge),
            "{file}"
        );
    }
}

fn a_file_at_25_mib_is_accepted_and_one_byte_over_is_refused() {
    for (file, magic) in [
        ("synthetic.pdf", PDF),
        ("synthetic.zip", ZIP),
        ("synthetic.txt", TEXT),
        ("synthetic", TEXT),
    ] {
        let at = padded(magic, FILE_MAX_BYTES);
        let over = padded(magic, FILE_MAX_BYTES + 1);
        assert_eq!(at.len() as u64, 25 * MIB);
        let n = name(file);
        assert_eq!(check(&n, &at, at.len() as u64), Ok(Kind::File), "{file}");
        assert_eq!(
            check(&n, &over, over.len() as u64),
            Err(FailReason::FileTooLarge),
            "{file}"
        );
    }
}

fn a_file_cloudroom_types_as_an_image_gets_the_image_limit() {
    for (file, magic) in [
        ("synthetic.svg", SVG),
        ("synthetic.bmp", BMP),
        ("synthetic.tiff", TIFF),
        ("synthetic.TIF", TIFF),
        ("synthetic.avif", &b"\0\0\0\x1cftypavif"[..]),
        ("synthetic.ico", TEXT),
    ] {
        let n = name(file);
        assert_eq!(limit(Kind::File, &n).max_bytes, IMAGE_MAX_BYTES, "{file}");
        let at = padded(magic, IMAGE_MAX_BYTES);
        let over = padded(magic, IMAGE_MAX_BYTES + 1);
        assert_eq!(check(&n, &at, at.len() as u64), Ok(Kind::File), "{file}");
        assert_eq!(
            check(&n, &over, over.len() as u64),
            Err(FailReason::ImageTypedFileTooLarge),
            "{file}"
        );
    }
    assert!(
        FailReason::ImageTypedFileTooLarge
            .message()
            .contains("10 MiB")
    );
    // Not in the table: the file limit.
    for file in [
        "synthetic.pdf",
        "synthetic.txt",
        "synthetic.zip",
        "synthetic",
    ] {
        assert_eq!(limit(Kind::File, &name(file)).max_bytes, FILE_MAX_BYTES);
    }
}

fn there_is_no_count_cap() {
    // 200 small files and 200 small images: every one is accepted on its
    // own, and nothing in the model counts them.
    let accepted = (0..200)
        .map(|i| {
            let file = name(&format!("synthetic-{i:03}.txt"));
            let image = name(&format!("synthetic-{i:03}.png"));
            check(&file, TEXT, TEXT.len() as u64) == Ok(Kind::File)
                && check(&image, PNG, 1024) == Ok(Kind::Image)
        })
        .filter(|ok| *ok)
        .count();
    assert_eq!(accepted, 200);
}
