//! ELF to UF2 conversion for RP2350 flash images.
//!
//! `elf2uf2-rs` 2.2 tags its output with the RP2040 family id, which the RP2350 boot ROM
//! refuses, so the few lines needed are here.

use std::collections::BTreeMap;
use std::fmt;

const FLASH_START: u32 = 0x1000_0000;
/// RP2354A: 2 MB of flash in the package.
const FLASH_END: u32 = FLASH_START + 2 * 1024 * 1024;
const PAGE_BYTES: usize = 256;

const BLOCK_BYTES: usize = 512;
const BLOCK_DATA_OFFSET: usize = 32;
const MAGIC_START_0: u32 = 0x0A32_4655;
const MAGIC_START_1: u32 = 0x9E5D_5157;
const MAGIC_END: u32 = 0x0AB1_6F30;
const FLAG_FAMILY_ID_PRESENT: u32 = 0x0000_2000;
/// "rp2350-arm-s": a secure Arm image, what the boot ROM runs by default.
pub const FAMILY_RP2350_ARM_SECURE: u32 = 0xE48B_FF59;

/// RP2354A: 520 kB of RAM.
const RAM_START: u32 = 0x2000_0000;
const RAM_END: u32 = RAM_START + 520 * 1024;
/// The boot ROM searches this much of the image for its image definition block.
const IMAGE_DEFINITION_SEARCH_BYTES: usize = 4096;
const BLOCK_START_MARKER: u32 = 0xFFFF_DED3;
const BLOCK_END_MARKER: u32 = 0xAB12_3579;
const ITEM_IMAGE_TYPE: u8 = 0x42;
const ITEM_LAST: u8 = 0xFF;
/// Image type flags: executable, secure mode, Arm, RP2350. Must agree with the UF2 family id.
const IMAGE_TYPE_ARM_SECURE_EXE: u16 = 0x1021;

const ELF_MAGIC: &[u8] = b"\x7FELF";
const ELF_CLASS_32: u8 = 1;
const ELF_LITTLE_ENDIAN: u8 = 1;
const ELF_HEADER_BYTES: usize = 52;
const PROGRAM_HEADER_BYTES: usize = 32;
const SEGMENT_LOAD: u32 = 1;

#[derive(Debug, PartialEq, Eq)]
pub enum Error {
    NotElf32LittleEndian,
    Truncated,
    /// A loadable segment lies outside the flash; holds its load address.
    SegmentOutsideFlash(u32),
    NothingToFlash,
    /// The vector table at the start of flash has no usable stack pointer or reset address.
    BadVectorTable,
    /// No well-formed image definition block in the first 4 kB: the boot ROM would not start this.
    NoImageDefinition,
    /// The image definition does not say "secure Arm executable for RP2350"; holds its flags.
    WrongImageType(u16),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotElf32LittleEndian => write!(f, "not a 32-bit little-endian ELF file"),
            Self::Truncated => write!(f, "the ELF file is cut short"),
            Self::SegmentOutsideFlash(address) => write!(f, "segment at {address:#010x} is outside the 2 MB flash"),
            Self::NothingToFlash => write!(f, "the ELF file has no loadable flash contents"),
            Self::BadVectorTable => write!(f, "the vector table at the start of flash is not valid"),
            Self::NoImageDefinition => write!(f, "no RP2350 image definition block in the first 4 kB of flash"),
            Self::WrongImageType(flags) => write!(
                f,
                "the image definition has type flags {flags:#06x}, not {IMAGE_TYPE_ARM_SECURE_EXE:#06x} (secure Arm executable)"
            ),
        }
    }
}

impl std::error::Error for Error {}

/// Converts a firmware ELF into UF2 blocks, one per 256-byte flash page that holds data.
pub fn elf_to_uf2(elf: &[u8]) -> Result<Vec<u8>, Error> {
    let pages = flash_pages(elf)?;
    if pages.is_empty() {
        return Err(Error::NothingToFlash);
    }
    let block_count = pages.len() as u32;
    let blocks = pages.iter().enumerate().map(|(number, (&address, page))| {
        uf2_block(
            BlockHeader {
                address,
                number: number as u32,
                block_count,
            },
            page,
        )
    });
    Ok(blocks.flatten().collect())
}

/// Checks what the RP2350 boot ROM needs before it runs an image: a vector table at the start
/// of flash and, within the first 4 kB, an image definition block for a secure Arm executable.
///
/// A UF2 that fails this copies fine and then never starts, so the converter refuses to write it.
pub fn check_bootable(elf: &[u8]) -> Result<(), Error> {
    let pages = flash_pages(elf)?;
    let head: Vec<u8> = (0..IMAGE_DEFINITION_SEARCH_BYTES / PAGE_BYTES)
        .map_while(|page| pages.get(&(FLASH_START + (page * PAGE_BYTES) as u32)))
        .flatten()
        .copied()
        .collect();
    check_vector_table(&head)?;
    let flags = image_type_flags(&head).ok_or(Error::NoImageDefinition)?;
    if flags != IMAGE_TYPE_ARM_SECURE_EXE {
        return Err(Error::WrongImageType(flags));
    }
    Ok(())
}

/// The first two vectors: a stack pointer inside RAM and a Thumb reset address inside flash.
fn check_vector_table(head: &[u8]) -> Result<(), Error> {
    let (Some(stack_pointer), Some(reset)) = (word_at(head, 0), word_at(head, 4)) else {
        return Err(Error::BadVectorTable);
    };
    let stack_in_ram = (RAM_START + 4..=RAM_END).contains(&stack_pointer) && stack_pointer % 4 == 0;
    let reset_in_flash = (FLASH_START..FLASH_END).contains(&reset) && reset % 2 == 1;
    if stack_in_ram && reset_in_flash {
        Ok(())
    } else {
        Err(Error::BadVectorTable)
    }
}

/// Finds a well-formed image definition block and returns the flags of its image type item.
fn image_type_flags(head: &[u8]) -> Option<u16> {
    (0..head.len())
        .step_by(4)
        .filter(|&offset| word_at(head, offset) == Some(BLOCK_START_MARKER))
        .find_map(|offset| flags_of_block(head, offset + 4))
}

/// Walks the items of a block that starts at `offset`. `None` if it is cut short or malformed.
fn flags_of_block(head: &[u8], mut offset: usize) -> Option<u16> {
    let mut flags = None;
    loop {
        let item = head.get(offset..offset + 4)?;
        if item[0] == ITEM_LAST {
            // After the last item: a link to the next block, then the end marker.
            return (word_at(head, offset + 8)? == BLOCK_END_MARKER)
                .then_some(flags)
                .flatten();
        }
        if item[0] == ITEM_IMAGE_TYPE {
            flags = Some(u16::from_le_bytes([item[2], item[3]]));
        }
        // Item types with the top bit set carry a two-byte size; the others one byte. In words.
        let size_words = if item[0] & 0x80 == 0 {
            usize::from(item[1])
        } else {
            usize::from(u16::from_le_bytes([item[1], item[2]]))
        };
        if size_words == 0 {
            return None;
        }
        offset += size_words * 4;
    }
}

fn word_at(bytes: &[u8], offset: usize) -> Option<u32> {
    let word = bytes.get(offset..offset + 4)?;
    Some(u32::from_le_bytes([word[0], word[1], word[2], word[3]]))
}

/// Flash contents by page address. Bytes no segment covers stay zero.
fn flash_pages(elf: &[u8]) -> Result<BTreeMap<u32, [u8; PAGE_BYTES]>, Error> {
    let mut pages = BTreeMap::new();
    for segment in load_segments(elf)? {
        let contents = elf.get(segment.file_range()).ok_or(Error::Truncated)?;
        if segment.address < FLASH_START || segment.address as usize + contents.len() > FLASH_END as usize {
            return Err(Error::SegmentOutsideFlash(segment.address));
        }
        for (offset, &byte) in contents.iter().enumerate() {
            let address = segment.address + offset as u32;
            let page: &mut [u8; PAGE_BYTES] = pages
                .entry(address - address % PAGE_BYTES as u32)
                .or_insert([0; PAGE_BYTES]);
            page[address as usize % PAGE_BYTES] = byte;
        }
    }
    Ok(pages)
}

struct Segment {
    file_offset: u32,
    /// Where the bytes are stored (the ELF "physical" address), not where they run.
    address: u32,
    file_bytes: u32,
}

impl Segment {
    fn file_range(&self) -> std::ops::Range<usize> {
        self.file_offset as usize..self.file_offset as usize + self.file_bytes as usize
    }
}

/// The segments that carry bytes to store. Zero-initialised RAM has none and is skipped.
fn load_segments(elf: &[u8]) -> Result<Vec<Segment>, Error> {
    let header = elf.get(..ELF_HEADER_BYTES).ok_or(Error::Truncated)?;
    if &header[..4] != ELF_MAGIC || header[4] != ELF_CLASS_32 || header[5] != ELF_LITTLE_ENDIAN {
        return Err(Error::NotElf32LittleEndian);
    }
    let table_offset = u32_at(header, 0x1C) as usize;
    let entry_bytes = usize::from(u16_at(header, 0x2A)).max(PROGRAM_HEADER_BYTES);
    let entry_count = usize::from(u16_at(header, 0x2C));
    let mut segments = Vec::new();
    for index in 0..entry_count {
        let start = table_offset + index * entry_bytes;
        let entry = elf.get(start..start + PROGRAM_HEADER_BYTES).ok_or(Error::Truncated)?;
        let segment = Segment {
            file_offset: u32_at(entry, 4),
            address: u32_at(entry, 12),
            file_bytes: u32_at(entry, 16),
        };
        if u32_at(entry, 0) == SEGMENT_LOAD && segment.file_bytes > 0 {
            segments.push(segment);
        }
    }
    Ok(segments)
}

struct BlockHeader {
    address: u32,
    number: u32,
    block_count: u32,
}

fn uf2_block(header: BlockHeader, page: &[u8; PAGE_BYTES]) -> [u8; BLOCK_BYTES] {
    let words = [
        MAGIC_START_0,
        MAGIC_START_1,
        FLAG_FAMILY_ID_PRESENT,
        header.address,
        PAGE_BYTES as u32,
        header.number,
        header.block_count,
        FAMILY_RP2350_ARM_SECURE,
    ];
    let mut block = [0; BLOCK_BYTES];
    for (index, word) in words.into_iter().enumerate() {
        block[index * 4..][..4].copy_from_slice(&word.to_le_bytes());
    }
    block[BLOCK_DATA_OFFSET..][..PAGE_BYTES].copy_from_slice(page);
    block[BLOCK_BYTES - 4..].copy_from_slice(&MAGIC_END.to_le_bytes());
    block
}

fn u32_at(bytes: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes(bytes[offset..offset + 4].try_into().expect("a four-byte slice"))
}

fn u16_at(bytes: &[u8], offset: usize) -> u16 {
    u16::from_le_bytes(bytes[offset..offset + 2].try_into().expect("a two-byte slice"))
}

#[cfg(test)]
mod tests {
    use super::*;

    const SEGMENT_NOTE: u32 = 4;

    struct TestSegment {
        kind: u32,
        address: u32,
        contents: Vec<u8>,
    }

    fn load(address: u32, contents: &[u8]) -> TestSegment {
        TestSegment {
            kind: SEGMENT_LOAD,
            address,
            contents: contents.to_vec(),
        }
    }

    /// A minimal ELF32: header, program header table, then each segment's bytes.
    fn elf(segments: &[TestSegment]) -> Vec<u8> {
        let mut file = vec![0u8; ELF_HEADER_BYTES];
        file[..6].copy_from_slice(b"\x7FELF\x01\x01");
        file[0x1C..0x20].copy_from_slice(&(ELF_HEADER_BYTES as u32).to_le_bytes());
        file[0x2A..0x2C].copy_from_slice(&(PROGRAM_HEADER_BYTES as u16).to_le_bytes());
        file[0x2C..0x2E].copy_from_slice(&(segments.len() as u16).to_le_bytes());
        let mut contents_offset = ELF_HEADER_BYTES + segments.len() * PROGRAM_HEADER_BYTES;
        for segment in segments {
            let fields = [
                segment.kind,
                contents_offset as u32,
                0,
                segment.address,
                segment.contents.len() as u32,
                0,
                0,
                0,
            ];
            file.extend(fields.iter().flat_map(|field| field.to_le_bytes()));
            contents_offset += segment.contents.len();
        }
        segments.iter().for_each(|segment| file.extend(&segment.contents));
        file
    }

    fn word(block: &[u8], index: usize) -> u32 {
        u32_at(block, index * 4)
    }

    #[test]
    fn one_small_segment_becomes_one_padded_block() {
        let uf2 = elf_to_uf2(&elf(&[load(FLASH_START, &[1, 2, 3])])).unwrap();
        assert_eq!(uf2.len(), BLOCK_BYTES);
        let header: Vec<u32> = (0..8).map(|index| word(&uf2, index)).collect();
        assert_eq!(
            header,
            [0x0A324655, 0x9E5D5157, 0x2000, FLASH_START, 256, 0, 1, 0xE48BFF59]
        );
        assert_eq!(uf2[32..36], [1, 2, 3, 0]);
        assert_eq!(word(&uf2, 127), 0x0AB16F30);
    }

    #[test]
    fn a_segment_crossing_a_page_border_fills_two_numbered_blocks() {
        let uf2 = elf_to_uf2(&elf(&[load(FLASH_START + 254, &[0xAA; 4])])).unwrap();
        let (first, second) = uf2.split_at(BLOCK_BYTES);
        assert_eq!([word(first, 3), word(first, 5), word(first, 6)], [FLASH_START, 0, 2]);
        assert_eq!(
            [word(second, 3), word(second, 5), word(second, 6)],
            [FLASH_START + 256, 1, 2]
        );
        assert_eq!(first[32 + 254..32 + 256], [0xAA; 2]);
        assert_eq!(second[32..34], [0xAA; 2]);
    }

    #[test]
    fn two_segments_in_one_page_share_a_block() {
        let segments = [load(FLASH_START, &[1]), load(FLASH_START + 8, &[2])];
        let uf2 = elf_to_uf2(&elf(&segments)).unwrap();
        assert_eq!(uf2.len(), BLOCK_BYTES);
        assert_eq!((uf2[32], uf2[40]), (1, 2));
    }

    #[test]
    fn blocks_are_in_address_order_whatever_the_segment_order() {
        let segments = [load(FLASH_START + 0x1000, &[2]), load(FLASH_START, &[1])];
        let uf2 = elf_to_uf2(&elf(&segments)).unwrap();
        assert_eq!(
            [word(&uf2, 3), word(&uf2[BLOCK_BYTES..], 3)],
            [FLASH_START, FLASH_START + 0x1000]
        );
    }

    #[test]
    fn segments_that_are_not_loadable_or_hold_no_bytes_are_skipped() {
        let note = TestSegment {
            kind: SEGMENT_NOTE,
            address: 0,
            contents: vec![9],
        };
        let ram_bss = load(0x2000_0000, &[]);
        let uf2 = elf_to_uf2(&elf(&[note, ram_bss, load(FLASH_START, &[1])])).unwrap();
        assert_eq!(uf2.len(), BLOCK_BYTES);
    }

    #[test]
    fn the_last_flash_byte_is_accepted_and_the_next_one_is_not() {
        assert!(elf_to_uf2(&elf(&[load(FLASH_END - 1, &[1])])).is_ok());
        assert_eq!(
            elf_to_uf2(&elf(&[load(FLASH_END - 1, &[1, 2])])),
            Err(Error::SegmentOutsideFlash(FLASH_END - 1))
        );
    }

    #[test]
    fn a_segment_stored_in_ram_is_rejected() {
        assert_eq!(
            elf_to_uf2(&elf(&[load(0x2000_0000, &[1])])),
            Err(Error::SegmentOutsideFlash(0x2000_0000))
        );
    }

    #[test]
    fn a_file_that_is_not_elf32_is_rejected() {
        assert_eq!(elf_to_uf2(&[0; ELF_HEADER_BYTES]), Err(Error::NotElf32LittleEndian));
        let mut elf64 = elf(&[load(FLASH_START, &[1])]);
        elf64[4] = 2;
        assert_eq!(elf_to_uf2(&elf64), Err(Error::NotElf32LittleEndian));
    }

    #[test]
    fn cut_short_files_are_rejected() {
        let whole = elf(&[load(FLASH_START, &[1, 2, 3])]);
        assert_eq!(elf_to_uf2(&whole[..10]), Err(Error::Truncated));
        assert_eq!(elf_to_uf2(&whole[..ELF_HEADER_BYTES + 5]), Err(Error::Truncated));
        assert_eq!(elf_to_uf2(&whole[..whole.len() - 1]), Err(Error::Truncated));
    }

    #[test]
    fn an_elf_without_flash_contents_is_rejected() {
        assert_eq!(elf_to_uf2(&elf(&[])), Err(Error::NothingToFlash));
    }

    /// A vector table and the image definition block embassy-rp emits for a secure Arm executable.
    fn bootable_head() -> Vec<u8> {
        let words: [u32; 8] = [
            RAM_END,
            FLASH_START + 0x101,
            0,
            BLOCK_START_MARKER,
            0x1021_0142,
            0x0000_01FF,
            0,
            BLOCK_END_MARKER,
        ];
        words.iter().flat_map(|word| word.to_le_bytes()).collect()
    }

    fn with_word(mut head: Vec<u8>, index: usize, word: u32) -> Vec<u8> {
        head[index * 4..][..4].copy_from_slice(&word.to_le_bytes());
        head
    }

    fn check(head: &[u8]) -> Result<(), Error> {
        check_bootable(&elf(&[load(FLASH_START, head)]))
    }

    #[test]
    fn an_image_with_vectors_and_an_image_definition_is_bootable() {
        assert_eq!(check(&bootable_head()), Ok(()));
    }

    #[test]
    fn an_image_definition_after_other_items_is_found() {
        // A two-word item of another type sits between the image type and the last item.
        let mut head = bootable_head();
        head.truncate(5 * 4);
        for word in [0x0000_0203u32, 0x1234_5678, 0x0000_03FF, 0, BLOCK_END_MARKER] {
            head.extend(word.to_le_bytes());
        }
        assert_eq!(check(&head), Ok(()));
    }

    #[test]
    fn an_image_without_a_definition_block_is_refused() {
        let no_block = with_word(bootable_head(), 3, 0);
        assert_eq!(check(&no_block), Err(Error::NoImageDefinition));
    }

    #[test]
    fn a_block_without_its_end_marker_is_refused() {
        let unterminated = with_word(bootable_head(), 7, 0);
        assert_eq!(check(&unterminated), Err(Error::NoImageDefinition));
        let mut cut_short = bootable_head();
        cut_short.truncate(6 * 4);
        assert_eq!(check(&cut_short), Err(Error::NoImageDefinition));
    }

    #[test]
    fn a_definition_beyond_the_first_four_kilobytes_is_not_seen() {
        let mut late = with_word(bootable_head(), 3, 0);
        late.resize(IMAGE_DEFINITION_SEARCH_BYTES, 0);
        late.extend(&bootable_head()[3 * 4..]);
        assert_eq!(check(&late), Err(Error::NoImageDefinition));
    }

    #[test]
    fn an_image_for_another_cpu_or_security_mode_is_refused() {
        // 0x1101: executable, RISC-V, RP2350.
        let riscv = with_word(bootable_head(), 4, 0x1101_0142);
        assert_eq!(check(&riscv), Err(Error::WrongImageType(0x1101)));
    }

    #[test]
    fn a_stack_pointer_outside_ram_or_an_arm_mode_reset_vector_is_refused() {
        assert_eq!(
            check(&with_word(bootable_head(), 0, FLASH_START)),
            Err(Error::BadVectorTable)
        );
        assert_eq!(
            check(&with_word(bootable_head(), 0, RAM_END + 4)),
            Err(Error::BadVectorTable)
        );
        assert_eq!(
            check(&with_word(bootable_head(), 1, FLASH_START + 0x100)),
            Err(Error::BadVectorTable)
        );
        assert_eq!(check(&[1, 2, 3]), Err(Error::BadVectorTable));
    }

    #[test]
    fn an_image_that_does_not_start_at_the_start_of_flash_is_refused() {
        let moved = elf(&[load(FLASH_START + 0x1000, &bootable_head())]);
        assert_eq!(check_bootable(&moved), Err(Error::BadVectorTable));
    }
}
