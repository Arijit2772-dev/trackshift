import socket
import os
import hashlib
import json
import sys
from pathlib import Path
import time




# -------------------------------------------------
# Status tracking for dashboard
# -------------------------------------------------
STATUS_PATH = Path(__file__).parent / "receiver_status.json"

def update_receiver_status(**kwargs):
    """Write live receiver status for the web monitor."""
    status = {
        "role": "receiver",
        "state": "waiting",
        "last_file": None,
        "files_received": 0,
        "expected_files": 0,
        "bytes_received_current_file": 0,
        "current_file_size": 0,
        "error_message": None,
        "last_update": None,
    }

    if STATUS_PATH.exists():
        try:
            with STATUS_PATH.open() as f:
                status.update(json.load(f))
        except Exception:
            pass

    status.update(kwargs)
    status["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with STATUS_PATH.open("w") as f:
        json.dump(status, f, indent=2)









# Add parent directory to path to import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import get_config, get_logger, setup_logging_from_config

# Initialize configuration and logging
config = get_config()
setup_logging_from_config(config)
logger = get_logger("receiver")

MANIFEST_FILE = "manifest.json"


def recv_line(conn):
    """
    Receive a line of text from connection (terminated by newline)

    Args:
        conn: Socket connection

    Returns:
        Decoded string or None if connection closed
    """
    data = b""
    while True:
        try:
            ch = conn.recv(1)
            if not ch:
                logger.debug("Connection closed during recv_line")
                return None
            if ch == b"\n":
                break
            data += ch
        except Exception as e:
            logger.error(f"Error receiving line: {e}")
            return None
    return data.decode()


def calculate_hash_file(path):
    """
    Compute SHA256 hash of a file (used for encrypted chunks)

    Args:
        path: File path to hash

    Returns:
        SHA256 hash as hex string
    """
    logger.debug(f"Calculating hash for: {path}")
    h = hashlib.sha256()
    buffer_size = config.buffer_size

    try:
        with open(path, "rb") as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                h.update(data)
        hash_value = h.hexdigest()
        logger.debug(f"Hash calculated: {hash_value[:16]}...")
        return hash_value
    except Exception as e:
        logger.error(f"Error calculating hash for {path}: {e}")
        raise


def load_expected_hashes():
    """
    Read manifest.json and build {chunk_name: expected_hash} mapping

    Returns:
        Dictionary mapping chunk filenames to their expected hashes
        Also returns manifest for priority information
    """
    if not os.path.exists(MANIFEST_FILE):
        logger.warning("manifest.json not found yet, cannot validate chunks")
        if config.show_progress:
            print("⚠ manifest.json not found yet, cannot validate chunks.")
        return {}, None

    try:
        with open(MANIFEST_FILE, "r") as f:
            manifest = json.load(f)

        expected = {}
        for ch in manifest.get("chunks", []):
            expected[ch["name"]] = ch["hash"]

        # Log manifest details
        logger.info(f"Loaded manifest: {manifest.get('original_filename', 'unknown')}")
        logger.info(f"Total chunks expected: {len(manifest.get('chunks', []))}")

        if "priority" in manifest:
            priority = manifest["priority"]
            priority_name = manifest.get("priority_name", "UNKNOWN")
            logger.info(f"File priority: {priority} ({priority_name})")

            if config.show_progress:
                print(f"✔ Loaded manifest: {manifest.get('original_filename')}")
                print(f"  Priority: {priority} ({priority_name})")
                print(f"  Expected chunks: {len(manifest.get('chunks', []))}")

        return expected, manifest

    except Exception as e:
        logger.error(f"Error loading manifest: {e}")
        return {}, None


def start_server():
    """
    Start receiver server and accept incoming file transfers
    """
    host = config.receiver_host
    port = config.port
    buffer_size = config.buffer_size

    logger.info("Starting Smart File Transfer System - Receiver")
    logger.info(f"Listening on {host}:{port}")

    # Initialize status
    update_receiver_status(state="waiting")

    print("=" * 60)
    print("SMART FILE TRANSFER SYSTEM - Receiver")
    print("=" * 60)
    print(f"\n📡 Waiting for connections on {host}:{port}...")
    print(f"   Buffer size: {buffer_size} bytes")
    print(f"   Timeout: {config.timeout}s" if config.timeout else "   Timeout: None")
    print("\nPress Ctrl+C to stop.\n")

    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)

        logger.info("Server socket created and listening")

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"❌ Error: Could not start server on {host}:{port}")
        print(f"   {e}")
        return

    try:
        conn, addr = server.accept()
        logger.info(f"Connection established with {addr[0]}:{addr[1]}")
        print(f"🔗 Connection established with {addr[0]}:{addr[1]}")
        print("=" * 60)

        # Update status - connected
        update_receiver_status(state="connected")

        if config.timeout:
            conn.settimeout(config.timeout)

        expected_hashes = {}
        manifest_received = False
        manifest = None
        files_received = 0
        total_bytes = 0

        while True:
            header = recv_line(conn)
            if header is None:
                logger.warning("Connection closed by sender")
                if config.show_progress:
                    print("\n⚠ Connection closed by sender.")
                break

            if header == "DONE":
                logger.info("Transfer completed successfully")
                if config.show_progress:
                    print("\n" + "=" * 60)
                    print("✔ Transfer completed successfully!")
                    print(f"  Files received: {files_received}")
                    print(f"  Total bytes: {total_bytes:,}")
                    print("=" * 60)
                update_receiver_status(
                    state="completed",
                    files_received=files_received,
                    error_message=None
                )
                break

            try:
                filename, size_str = header.split("|")
                size = int(size_str)
            except ValueError as e:
                logger.error(f"Invalid header format: {header}")
                continue

            logger.info(f"Receiving: {filename} ({size:,} bytes)")
            if config.show_progress:
                print(f"\n⬇ Receiving: {filename} ({size/1_000_000:.2f} MB)")

            # Update status - receiving file
            update_receiver_status(
                state="receiving",
                last_file=filename,
                current_file_size=size,
                bytes_received_current_file=0,
                files_received=files_received
            )

            # Receive file data
            remaining = size
            bytes_received_so_far = 0
            try:
                with open(filename, "wb") as f:
                    while remaining > 0:
                        chunk_data = conn.recv(min(buffer_size, remaining))
                        if not chunk_data:
                            logger.error("Connection lost while receiving file data")
                            if config.show_progress:
                                print("⚠ Connection lost while receiving file data.")
                            update_receiver_status(
                                state="error",
                                error_message="Connection lost while receiving file"
                            )
                            conn.close()
                            server.close()
                            return
                        f.write(chunk_data)
                        remaining -= len(chunk_data)
                        bytes_received_so_far += len(chunk_data)

                        # Update status with progress
                        update_receiver_status(
                            bytes_received_current_file=bytes_received_so_far
                        )

                files_received += 1
                total_bytes += size
                logger.info(f"File saved: {filename}")

            except Exception as e:
                logger.error(f"Error receiving file {filename}: {e}")
                conn.sendall(b"BAD")
                continue

            # Special case: manifest.json itself
            if filename == MANIFEST_FILE:
                manifest_received = True
                expected_hashes, manifest = load_expected_hashes()
                conn.sendall(b"OK")
                logger.info(f"Manifest received and loaded")

                # Update expected files count
                if manifest:
                    expected_files = len(manifest.get('chunks', []))
                    update_receiver_status(expected_files=expected_files)

                continue

            # For other files (chunks), verify hash if we have manifest
            if manifest_received and filename in expected_hashes:
                actual_hash = calculate_hash_file(filename)
                expected_hash = expected_hashes[filename]

                if actual_hash == expected_hash:
                    logger.info(f"[OK] {filename} - Hash verified")
                    if config.show_progress:
                        print(f"✔ [OK] Hash verified")
                    conn.sendall(b"OK")
                else:
                    logger.warning(
                        f"[BAD] {filename} - Hash mismatch "
                        f"(expected {expected_hash[:8]}..., got {actual_hash[:8]}...)"
                    )
                    if config.show_progress:
                        print(f"✗ [BAD] Hash mismatch!")
                        print(f"  Expected: {expected_hash[:16]}...")
                        print(f"  Got:      {actual_hash[:16]}...")
                    conn.sendall(b"BAD")
            else:
                # If we don't know this file from manifest, accept it
                logger.warning(f"No expected hash for {filename}, accepting by default")
                if config.show_progress:
                    print(f"[WARN] No expected hash, accepting by default")
                conn.sendall(b"OK")

    except KeyboardInterrupt:
        logger.info("Server stopped by user (Ctrl+C)")
        print("\n\n⚠ Server stopped by user (Ctrl+C)")
        update_receiver_status(state="stopped", error_message="Stopped by user")

    except Exception as e:
        logger.exception(f"Server error: {e}")
        print(f"\n❌ Error: {e}")
        update_receiver_status(state="error", error_message=str(e))

    finally:
        try:
            conn.close()
            logger.debug("Connection closed")
        except:
            pass

        try:
            server.close()
            logger.debug("Server socket closed")
        except:
            pass

        logger.info("Receiver shutdown complete")


if __name__ == "__main__":
    start_server()

