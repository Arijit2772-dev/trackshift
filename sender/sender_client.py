import os
import socket
import time
import json
import sys
from pathlib import Path

STATUS_PATH = Path(__file__).parent / "sender_status.json"

def update_sender_status(**kwargs):
    """Write live sender status for the web monitor."""
    status = {
        "role": "sender",
        "state": "idle",
        "current_file": None,
        "current_index": 0,
        "total_files": 0,
        "bytes_sent_current_file": 0,
        "current_file_size": 0,
        "files_sent": 0,
        "error_message": None,
        "last_update": None,
    }

    if STATUS_PATH.exists():
        try:
            with STATUS_PATH.open() as f:
                status.update(json.load(f))
        except Exception:
            # ignore corrupt file, overwrite
            pass

    status.update(kwargs)
    status["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with STATUS_PATH.open("w") as f:
        json.dump(status, f)











# Add parent directory to path to import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import get_config, get_logger, setup_logging_from_config

# Initialize configuration and logging
config = get_config()
setup_logging_from_config(config)
logger = get_logger("sender")

MANIFEST_FILE = "manifest.json"


def progress_bar(sent, total, start_time):
    percent = sent / total if total > 0 else 0
    bar_length = 30
    filled = int(percent * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)

    elapsed = time.time() - start_time
    speed = sent / elapsed if elapsed > 0 else 0
    eta = (total - sent) / speed if speed > 0 else 0

    speed_mb = speed / (1024 * 1024)
    return f"{bar} {percent*100:5.1f}% — {speed_mb:4.2f} MB/s — ETA: {eta:0.1f}s"


def load_state():
    """Load resume state from transfer_state.json (if exists)."""
    state_file = config.state_file
    if not os.path.exists(state_file):
        logger.debug(f"No existing state file found: {state_file}")
        return {"completed_files": []}
    try:
        with open(state_file, "r") as f:
            state = json.load(f)
        if "completed_files" not in state:
            state["completed_files"] = []
        logger.info(f"Loaded state file: {len(state['completed_files'])} files already completed")
        return state
    except Exception as e:
        # if state file corrupted, start fresh
        logger.warning(f"Could not load state file, starting fresh: {e}")
        return {"completed_files": []}


def save_state(state):
    """Save resume state to transfer_state.json."""
    state_file = config.state_file
    try:
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"State saved: {len(state.get('completed_files', []))} completed files")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def send_file_once(conn, filename, size):
    """Send the file exactly once (no retry here)."""
    header = f"{filename}|{size}\n".encode()
    conn.sendall(header)

    logger.info(f"Sending: {filename} ({size/1_000_000:.2f} MB)")
    if config.show_progress:
        print(f"\n📤 Sending: {filename} ({size/1_000_000:.2f} MB)")

    sent = 0
    start_time = time.time()
    buffer_size = config.buffer_size

    with open(filename, "rb") as f:
        while True:
            data = f.read(buffer_size)
            if not data:
                break
            conn.sendall(data)
            sent += len(data)

            if config.show_progress:
                print("\r" + progress_bar(sent, size, start_time), end="")

    if config.show_progress:
        print()  # newline after progress bar

    logger.info(f"Finished sending bytes for {filename}")

    response = conn.recv(1024).decode().strip()
    logger.info(f"Receiver response for {filename}: {response}")

    if config.show_progress:
        print(f"✔ Receiver response: {response}")

    return response


def send_file_with_retry(conn, filename):
    """Send a file with retry logic"""
    size = os.path.getsize(filename)
    max_retries = config.max_retries

    for attempt in range(1, max_retries + 1):
        logger.info(f"Attempt {attempt}/{max_retries} to send {filename}")
        if config.show_progress and attempt > 1:
            print(f"\n🔁 Retry attempt {attempt}/{max_retries} for {filename}")

        resp = send_file_once(conn, filename, size)

        if resp == "OK":
            logger.info(f"{filename} sent successfully on attempt {attempt}")
            if config.show_progress:
                print(f"✅ {filename} sent successfully")
            return True
        else:
            logger.warning(f"{filename} not accepted (response: {resp})")
            if config.show_progress:
                print(f"⚠ {filename} not accepted (response: {resp})")

    logger.error(f"Failed to send {filename} after {max_retries} attempts")
    if config.show_progress:
        print(f"❌ Failed to send {filename} after {max_retries} attempts")
    return False


def load_manifest():
    """Load manifest to get priority information"""
    if not os.path.exists(MANIFEST_FILE):
        logger.warning(f"Manifest file not found: {MANIFEST_FILE}")
        return None

    try:
        with open(MANIFEST_FILE, 'r') as f:
            manifest = json.load(f)
        logger.info(f"Manifest loaded: {manifest.get('original_filename', 'unknown')}")
        if 'priority' in manifest:
            priority_name = manifest.get('priority_name', 'UNKNOWN')
            logger.info(f"File priority: {manifest['priority']} ({priority_name})")
        return manifest
    except Exception as e:
        logger.error(f"Failed to load manifest: {e}")
        return None


def sort_files_by_priority(files, manifest):
    """
    Sort files by priority from manifest
    Manifest is sent first, then chunks sorted by priority

    Args:
        files: List of filenames
        manifest: Manifest dictionary

    Returns:
        Sorted list of files
    """
    if not manifest or not config.priority_enabled:
        # If no manifest or priority disabled, return as-is
        return files

    # Separate manifest from chunks
    manifest_files = [f for f in files if f == MANIFEST_FILE]
    chunk_files = [f for f in files if f.startswith("echunk_")]

    # Get default priority
    default_priority = manifest.get('priority', config.default_priority)

    # Create priority mapping for chunks
    chunk_priority_map = {}
    for chunk_info in manifest.get('chunks', []):
        chunk_name = chunk_info.get('name')
        chunk_priority = chunk_info.get('priority', default_priority)
        if chunk_name:
            chunk_priority_map[chunk_name] = chunk_priority

    # Sort chunks by priority (lower number = higher priority)
    sorted_chunks = sorted(chunk_files, key=lambda f: chunk_priority_map.get(f, default_priority))

    # Manifest first, then sorted chunks
    return manifest_files + sorted_chunks


def main():
    logger.info("Starting Smart File Transfer System - Sender")
    print("=" * 60)
    print("SMART FILE TRANSFER SYSTEM - Sender")
    print("=" * 60)

    # Initialize status
    update_sender_status(state="idle")

    # Get receiver address
    host = input("\nEnter receiver IP (default: 127.0.0.1): ").strip()
    if not host:
        host = "127.0.0.1"

    # Ask for demo delay
    delay_input = input("Add delay between files in seconds (0 for no delay, 3-5 recommended for demo): ").strip()
    try:
        delay_between_files = int(delay_input) if delay_input else 0
    except:
        delay_between_files = 0

    if delay_between_files > 0:
        print(f"\n⏱️  Will pause {delay_between_files} seconds between files (press Ctrl+C to interrupt!)")

    port = config.port
    logger.info(f"Target receiver: {host}:{port}")
    if delay_between_files > 0:
        logger.info(f"Demo mode: {delay_between_files}s delay between files")

    # Load existing resume state (if any)
    if config.enable_resume:
        state = load_state()
        completed_files = set(state.get("completed_files", []))
    else:
        logger.info("Resume capability disabled")
        state = {"completed_files": []}
        completed_files = set()

    # Load manifest for priority information
    manifest = load_manifest()

    # Connect to receiver
    try:
        logger.info(f"Connecting to receiver at {host}:{port}...")
        update_sender_status(state="connecting")
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if config.timeout:
            conn.settimeout(config.timeout)
        conn.connect((host, port))
        logger.info("Connected successfully")
        print(f"\n🔗 Connected to receiver at {host}:{port}")
        update_sender_status(state="connected")
    except Exception as e:
        logger.error(f"Failed to connect to receiver: {e}")
        print(f"\n❌ Error: Could not connect to {host}:{port}")
        print(f"   {e}")
        update_sender_status(state="error", error_message=str(e))
        return

    # find all encrypted chunks
    chunk_files = sorted([f for f in os.listdir() if f.startswith("echunk_")])

    files_to_send = []

    # send manifest first if it exists
    if os.path.exists(MANIFEST_FILE):
        files_to_send.append(MANIFEST_FILE)

    files_to_send.extend(chunk_files)

    # Sort by priority if enabled
    if config.priority_enabled and manifest:
        logger.info("Sorting files by priority...")
        files_to_send = sort_files_by_priority(files_to_send, manifest)

    if not files_to_send:
        logger.warning("No files found to send")
        print("\n⚠ No files found to send!")
        print("   Run chunker_compress_encrypt.py first to prepare files.")
        update_sender_status(state="error", error_message="No files found to send")
        conn.close()
        return

    logger.info(f"Found {len(files_to_send)} files to send")
    print(f"\nFound {len(files_to_send)} files to send:")
    for f in files_to_send:
        mark = "[DONE]" if f in completed_files else "[PENDING]"
        print(f"  {mark} {f}")

    # Update status with total files
    update_sender_status(
        state="preparing",
        total_files=len(files_to_send),
        files_sent=len(completed_files)
    )

    print("\n" + "=" * 60)
    all_ok = True
    total_files = len(files_to_send)
    sent_count = 0

    for idx, f in enumerate(files_to_send, 1):
        if f in completed_files:
            logger.info(f"Skipping {f} (already completed)")
            if config.show_progress:
                print(f"\n⏭ Skipping {f} (already completed in previous session)")
            sent_count += 1
            continue

        logger.info(f"Processing file {idx}/{total_files}: {f}")

        # Update status before sending
        file_size = os.path.getsize(f)
        update_sender_status(
            state="sending",
            current_file=f,
            current_index=idx,
            total_files=total_files,
            current_file_size=file_size,
            bytes_sent_current_file=0,
            files_sent=sent_count
        )

        ok = send_file_with_retry(conn, f)

        if not ok:
            all_ok = False
            logger.error(f"Failed to send {f}")
            if config.show_progress:
                print(f"❌ Giving up on {f}, moving to next")
            update_sender_status(
                state="error",
                error_message=f"Failed to send {f}"
            )
        else:
            # mark as completed and save state
            sent_count += 1
            if config.enable_resume:
                completed_files.add(f)
                state["completed_files"] = sorted(list(completed_files))
                save_state(state)
                logger.debug(f"State updated: {f} marked as completed")

            # Update status after successful send
            update_sender_status(
                state="sending",
                files_sent=sent_count,
                bytes_sent_current_file=file_size
            )

            # Add delay between files if requested (for demo purposes)
            if delay_between_files > 0 and idx < total_files:
                logger.info(f"Demo delay: waiting {delay_between_files}s before next file")
                if config.show_progress:
                    print(f"\n⏸️  Pausing {delay_between_files} seconds... (press Ctrl+C to test interruption)")
                time.sleep(delay_between_files)

    # Send completion signal
    logger.info("Sending DONE signal")
    conn.sendall(b"DONE\n")

    print("\n" + "=" * 60)
    if all_ok:
        logger.info("Transfer completed successfully")
        print("🎉 Transfer Complete! All files sent successfully.")
        update_sender_status(
            state="completed",
            files_sent=sent_count,
            total_files=total_files,
            error_message=None
        )
    else:
        logger.warning("Transfer completed with some failures")
        print("⚠ Transfer Complete (with some failures)")
        print("   Check sfts.log for details")
        update_sender_status(
            state="completed_with_errors",
            files_sent=sent_count,
            total_files=total_files,
            error_message="Some files failed to send"
        )

    print(f"   Files sent: {sent_count}/{total_files}")
    print("=" * 60)

    conn.close()
    logger.info("Connection closed")
    


if __name__ == "__main__":
    main()
