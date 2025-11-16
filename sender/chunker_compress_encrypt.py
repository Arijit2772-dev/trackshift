import hashlib
import zlib
import json
import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet

# Add parent directory to path to import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import get_config, get_logger, setup_logging_from_config

# Initialize configuration and logging
config = get_config()
setup_logging_from_config(config)
logger = get_logger("chunker")

MANIFEST_FILE = "manifest.json"


def load_key():
    """Load encryption key from file"""
    key_file = config.key_file
    logger.debug(f"Loading encryption key from: {key_file}")
    try:
        with open(key_file, "rb") as f:
            key = f.read()
        logger.info("Encryption key loaded successfully")
        return key
    except FileNotFoundError:
        logger.error(f"Encryption key file not found: {key_file}")
        raise


def calculate_hash(data):
    return hashlib.sha256(data).hexdigest()


def split_compress_encrypt(filepath, priority=None):
    """
    Split, compress, and encrypt a file into chunks

    Args:
        filepath: Path to the file to process
        priority: Priority level (1-4, where 1=CRITICAL, 4=LOW)
                 If None, uses default from config

    Returns:
        Manifest dictionary
    """
    logger.info(f"Starting chunking process for: {filepath}")

    # Get configuration values
    chunk_size = config.chunk_size
    compression_level = config.compression_level
    if priority is None:
        priority = config.default_priority

    # Validate priority
    if priority not in [1, 2, 3, 4]:
        logger.warning(f"Invalid priority {priority}, using default {config.default_priority}")
        priority = config.default_priority

    priority_name = config.priority_levels.get(priority, "UNKNOWN")
    logger.info(f"File priority: {priority} ({priority_name})")
    logger.info(f"Chunk size: {chunk_size} bytes ({chunk_size // (1024*1024)} MB)")
    logger.info(f"Compression level: {compression_level}")

    key = load_key()
    fernet = Fernet(key)

    chunks_meta = []  # will hold dicts about each chunk

    # for original file hash (end-to-end)
    original_hasher = hashlib.sha256()
    total_raw_bytes = 0

    logger.info("Reading and processing file chunks...")

    with open(filepath, "rb") as f:
        chunk_id = 0
        while True:
            # 1) Read raw data from original file
            raw_chunk = f.read(chunk_size)
            if not raw_chunk:
                break

            total_raw_bytes += len(raw_chunk)
            original_hasher.update(raw_chunk)

            # 2) Compress the raw chunk
            if config.compression_enabled:
                compressed_chunk = zlib.compress(raw_chunk, level=compression_level)
            else:
                compressed_chunk = raw_chunk
                logger.debug("Compression disabled, skipping")

            # 3) Encrypt the compressed data
            if config.encryption_enabled:
                encrypted_chunk = fernet.encrypt(compressed_chunk)
            else:
                encrypted_chunk = compressed_chunk
                logger.warning("Encryption disabled - NOT RECOMMENDED for production!")

            # 4) Save encrypted chunk
            filename = f"echunk_{chunk_id}.bin"
            with open(filename, "wb") as chunk_file:
                chunk_file.write(encrypted_chunk)

            # 5) Hash the ENCRYPTED data (ciphertext)
            chunk_hash = calculate_hash(encrypted_chunk)

            # Calculate compression ratio
            compression_ratio = (1 - len(compressed_chunk) / len(raw_chunk)) * 100

            chunks_meta.append(
                {
                    "index": chunk_id,
                    "name": filename,
                    "size": len(encrypted_chunk),
                    "hash": chunk_hash,
                    "priority": priority,  # Add priority to each chunk
                }
            )

            logger.info(
                f"Chunk {chunk_id}: {filename} | "
                f"Raw: {len(raw_chunk):,} bytes | "
                f"Compressed: {len(compressed_chunk):,} bytes ({compression_ratio:.1f}% reduction) | "
                f"Encrypted: {len(encrypted_chunk):,} bytes"
            )

            chunk_id += 1

    original_hash = original_hasher.hexdigest()

    logger.info(f"Total chunks created: {chunk_id}")
    logger.info(f"Original file size: {total_raw_bytes:,} bytes")
    logger.info(f"Original file hash: {original_hash}")

    manifest = {
        "original_filename": os.path.basename(filepath),
        "original_size": total_raw_bytes,
        "original_hash": original_hash,
        "chunk_size": chunk_size,
        "hash_algorithm": "sha256",
        "priority": priority,  # Add priority to manifest
        "priority_name": priority_name,
        "compression_enabled": config.compression_enabled,
        "encryption_enabled": config.encryption_enabled,
        "chunks": chunks_meta,
    }

    with open(MANIFEST_FILE, "w") as m:
        json.dump(manifest, m, indent=2)

    logger.info(f"Manifest saved as {MANIFEST_FILE}")
    logger.info("✔ Chunking process completed successfully")

    return manifest


if __name__ == "__main__":
    print("=" * 60)
    print("SMART FILE TRANSFER SYSTEM - File Chunker")
    print("=" * 60)

    filename = input("\nEnter file path: ").strip()

    # Check if file exists
    if not os.path.exists(filename):
        logger.error(f"File not found: {filename}")
        print(f"Error: File not found: {filename}")
        sys.exit(1)

    # Ask for priority
    print("\nSelect priority level:")
    print("  1 - CRITICAL (highest priority)")
    print("  2 - HIGH")
    print("  3 - NORMAL (default)")
    print("  4 - LOW")

    priority_input = input(f"Enter priority (1-4) [default: 3]: ").strip()

    if priority_input == "":
        priority = 3
    else:
        try:
            priority = int(priority_input)
            if priority not in [1, 2, 3, 4]:
                print(f"Invalid priority, using default (3)")
                priority = 3
        except ValueError:
            print(f"Invalid input, using default priority (3)")
            priority = 3

    print("\n" + "=" * 60)
    try:
        manifest = split_compress_encrypt(filename, priority=priority)
        print("=" * 60)
        print("✔ SUCCESS! Files are ready to send.")
        print(f"  Manifest: {MANIFEST_FILE}")
        print(f"  Chunks created: {len(manifest['chunks'])}")
        print(f"  Priority: {manifest['priority']} ({manifest['priority_name']})")
        print("=" * 60)
    except Exception as e:
        logger.exception("Failed to process file")
        print(f"\n✗ ERROR: {e}")
        sys.exit(1)

