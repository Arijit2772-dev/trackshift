import os
import hashlib
import zlib
import json
import sys
from pathlib import Path
from cryptography.fernet import Fernet

# Add parent directory to path to import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import get_config, get_logger, setup_logging_from_config

# Initialize configuration and logging
config = get_config()
setup_logging_from_config(config)
logger = get_logger("reassemble")

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


def load_manifest(path=MANIFEST_FILE):
    """
    Read manifest.json and return it as a dict

    Args:
        path: Path to manifest file

    Returns:
        Manifest dictionary or None if not found
    """
    logger.info(f"Loading manifest from: {path}")
    try:
        with open(path, "r") as f:
            manifest = json.load(f)

        # Log manifest details
        logger.info(f"Manifest loaded: {manifest.get('original_filename', 'unknown')}")
        logger.info(f"Total chunks: {len(manifest.get('chunks', []))}")

        if "priority" in manifest:
            priority_name = manifest.get("priority_name", "UNKNOWN")
            logger.info(f"File priority: {manifest['priority']} ({priority_name})")

        return manifest
    except FileNotFoundError:
        logger.error(f"Manifest file not found: {path}")
        print(f"❌ Manifest file '{path}' not found.")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid manifest JSON: {e}")
        print(f"❌ Invalid manifest file: {e}")
        return None


def calculate_hash_file(path):
    """
    Compute SHA256 hash of the *encrypted* chunk file

    Args:
        path: Path to file

    Returns:
        SHA256 hash as hex string
    """
    logger.debug(f"Calculating hash for encrypted chunk: {path}")
    h = hashlib.sha256()
    buffer_size = config.buffer_size

    with open(path, "rb") as f:
        while True:
            data = f.read(buffer_size)
            if not data:
                break
            h.update(data)

    hash_value = h.hexdigest()
    logger.debug(f"Hash: {hash_value[:16]}...")
    return hash_value


def verify_chunks(manifest):
    """
    Check each encrypted chunk using the manifest

    Args:
        manifest: Manifest dictionary

    Returns:
        Tuple of (all_ok: bool, status_dict: dict)
    """
    status = {}
    all_ok = True

    logger.info("Starting chunk verification")
    print("\n" + "=" * 60)
    print("VERIFYING ENCRYPTED CHUNKS")
    print("=" * 60)

    chunks = manifest.get("chunks", [])
    for idx, ch in enumerate(chunks, 1):
        name = ch["name"]
        expected_hash = ch["hash"]

        print(f"\n[{idx}/{len(chunks)}] Checking: {name}")
        logger.info(f"Verifying chunk {idx}/{len(chunks)}: {name}")

        if not os.path.exists(name):
            logger.error(f"Chunk missing: {name}")
            print(f"  ✗ [MISSING] File not found")
            status[name] = "missing"
            all_ok = False
            continue

        actual_hash = calculate_hash_file(name)

        if actual_hash == expected_hash:
            logger.info(f"Chunk OK: {name}")
            print(f"  ✓ [OK] Hash verified")
            status[name] = "ok"
        else:
            logger.warning(f"Chunk corrupted: {name}")
            print(f"  ✗ [BAD] Hash mismatch")
            print(f"     Expected: {expected_hash[:16]}...")
            print(f"     Got:      {actual_hash[:16]}...")
            status[name] = "bad"
            all_ok = False

    print("=" * 60)
    logger.info(f"Chunk verification complete: {'All OK' if all_ok else 'FAILED'}")

    return all_ok, status


def calculate_hash_file_raw(path):
    """
    Compute SHA256 hash of the raw (decrypted) final file

    Args:
        path: Path to file

    Returns:
        SHA256 hash as hex string
    """
    logger.info(f"Calculating final file hash: {path}")
    h = hashlib.sha256()
    buffer_size = config.buffer_size

    with open(path, "rb") as f:
        while True:
            data = f.read(buffer_size)
            if not data:
                break
            h.update(data)

    hash_value = h.hexdigest()
    logger.info(f"Final hash: {hash_value}")
    return hash_value


def reassemble(output_filename, manifest):
    """
    Verify OK → decrypt → decompress → reassemble original file

    Args:
        output_filename: Output file path
        manifest: Manifest dictionary
    """
    logger.info(f"Starting reassembly process: {output_filename}")

    print("\n" + "=" * 60)
    print("REASSEMBLING FILE")
    print("=" * 60)

    key = load_key()
    fernet = Fernet(key)

    # sort chunks by their index
    chunks = sorted(manifest.get("chunks", []), key=lambda c: c["index"])

    compression_enabled = manifest.get("compression_enabled", True)
    encryption_enabled = manifest.get("encryption_enabled", True)

    print(f"\nOutput file: {output_filename}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Compression: {'Enabled' if compression_enabled else 'Disabled'}")
    print(f"Encryption: {'Enabled' if encryption_enabled else 'Disabled'}")
    print("\nProcessing chunks...")

    try:
        with open(output_filename, "wb") as outfile:
            for idx, ch in enumerate(chunks, 1):
                chunk_name = ch["name"]
                print(f"\n[{idx}/{len(chunks)}] Processing: {chunk_name}")
                logger.info(f"Processing chunk {idx}/{len(chunks)}: {chunk_name}")

                with open(chunk_name, "rb") as infile:
                    data = infile.read()

                    # 1) Decrypt if encryption was enabled
                    if encryption_enabled:
                        logger.debug(f"Decrypting {chunk_name}")
                        data = fernet.decrypt(data)
                        print(f"  ✓ Decrypted")

                    # 2) Decompress if compression was enabled
                    if compression_enabled:
                        logger.debug(f"Decompressing {chunk_name}")
                        data = zlib.decompress(data)
                        print(f"  ✓ Decompressed")

                    # 3) Write to final file
                    bytes_written = outfile.write(data)
                    logger.debug(f"Written {bytes_written:,} bytes")
                    print(f"  ✓ Written {bytes_written:,} bytes")

        print("\n" + "=" * 60)
        print(f"✔ File reassembled: {output_filename}")

        file_size = os.path.getsize(output_filename)
        logger.info(f"Reassembled file size: {file_size:,} bytes")
        print(f"  Size: {file_size:,} bytes ({file_size/1_000_000:.2f} MB)")

    except Exception as e:
        logger.exception(f"Error during reassembly: {e}")
        print(f"\n❌ Error during reassembly: {e}")
        raise

    # Verify final file hash against original_hash
    orig_hash = manifest.get("original_hash")
    if orig_hash:
        logger.info("Verifying final file hash against original")
        print("\n" + "=" * 60)
        print("FINAL VERIFICATION")
        print("=" * 60)

        final_hash = calculate_hash_file_raw(output_filename)

        print(f"\nOriginal hash: {orig_hash}")
        print(f"Final hash:    {final_hash}")

        if final_hash == orig_hash:
            logger.info("✓ Final file hash matches original")
            print("\n✅ SUCCESS! File integrity verified.")
            print("   The reassembled file is identical to the original!")
            print("=" * 60)
        else:
            logger.error("✗ Final file hash does NOT match original!")
            print("\n❌ FAILURE! Hash mismatch!")
            print(f"   Expected: {orig_hash}")
            print(f"   Got:      {final_hash}")
            print("   The file may be corrupted!")
            print("=" * 60)
    else:
        logger.warning("No original hash in manifest for verification")
        print("\n⚠ Warning: No original hash in manifest to verify against.")
        print("=" * 60)


if __name__ == "__main__":
    logger.info("Starting Smart File Transfer System - File Reassembly")

    print("=" * 60)
    print("SMART FILE TRANSFER SYSTEM - File Reassembly")
    print("=" * 60)

    # Load manifest
    manifest = load_manifest()
    if manifest is None:
        logger.error("Cannot proceed without manifest")
        print("\n❌ Cannot proceed without manifest file.")
        print("   Make sure manifest.json exists in the current directory.")
        exit(1)

    # Display manifest info
    print(f"\nOriginal file: {manifest.get('original_filename', 'unknown')}")
    print(f"Original size: {manifest.get('original_size', 0):,} bytes")

    if "priority" in manifest:
        priority_name = manifest.get("priority_name", "UNKNOWN")
        print(f"Priority: {manifest['priority']} ({priority_name})")

    print(f"Total chunks: {len(manifest.get('chunks', []))}")

    # Verify chunks
    all_ok, status = verify_chunks(manifest)

    if not all_ok:
        logger.error("Chunk verification failed")
        print("\n" + "=" * 60)
        print("❌ VERIFICATION FAILED")
        print("=" * 60)
        print("\nSome chunks are missing or corrupted.")
        print("Cannot reassemble file safely.")
        print("\nFailed chunks:")
        for name, stat in status.items():
            if stat != "ok":
                print(f"  - {name}: {stat.upper()}")
        print("\nPlease re-transfer the failed chunks.")
        print("=" * 60)
        exit(1)
    else:
        logger.info("All chunks verified successfully")
        print("\n" + "=" * 60)
        print("✅ ALL CHUNKS VERIFIED")
        print("=" * 60)
        print("\nAll encrypted chunks are intact and verified.")
        print("Ready to reassemble the original file.")
        print("=" * 60)

        # Get output filename
        default_name = manifest.get("original_filename", "rebuilt_file.bin")
        print(f"\nDefault output filename: {default_name}")
        out_name = input("Enter output filename (or press Enter for default): ").strip()

        if not out_name:
            out_name = default_name
            logger.info(f"Using default filename: {out_name}")
        else:
            logger.info(f"Using custom filename: {out_name}")

        # Check if file exists
        if os.path.exists(out_name):
            print(f"\n⚠ Warning: File '{out_name}' already exists!")
            overwrite = input("Overwrite? (yes/no): ").strip().lower()
            if overwrite not in ["yes", "y"]:
                logger.info("User cancelled overwrite")
                print("\n❌ Operation cancelled by user.")
                exit(0)

        # Reassemble
        try:
            reassemble(out_name, manifest)
            logger.info("Reassembly completed successfully")
        except Exception as e:
            logger.exception("Reassembly failed")
            print(f"\n❌ Reassembly failed: {e}")
            exit(1)

