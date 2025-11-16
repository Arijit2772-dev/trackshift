# 🚀 Smart File Transfer System (SFTS)

**A fast, resilient file transfer system designed for unstable network connections**

Built for media studios, rural labs, mobile clinics, remote engineering sites, and any scenario requiring reliable file transfer over unreliable network links.

---

## ✨ Features

- **🔒 Secure**: AES-128 encryption with HMAC authentication
- **📦 Chunked Transfer**: Split large files into manageable pieces
- **🔄 Resume Capability**: Continue from where you left off after connection drops
- **⚡ Priority System**: Send critical files first
- **✅ Integrity Verification**: Dual-level SHA256 hashing ensures perfect reconstruction
- **📊 Real-time Progress**: Live progress bars with speed and ETA
- **🖥️ Web Monitoring**: Real-time web dashboard to monitor transfers
- **🗜️ Compression**: Automatic zlib compression reduces transfer time
- **⚙️ Configurable**: YAML-based configuration for different environments
- **📝 Comprehensive Logging**: Track every operation for debugging

---

## 📋 Requirements

- **Python 3.7+**
- **cryptography** library
- **PyYAML** library

---

## 🔧 Installation

### 1. Clone or Download

```bash
cd /path/to/sfts
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > sender/secret.key
```

**IMPORTANT**: Copy the same `secret.key` to both sender and receiver:

```bash
cp sender/secret.key receiver/secret.key
```

---

## 🚀 Quick Start

### Optional: Start Monitoring Dashboard

For real-time transfer monitoring, start the web dashboard:

```bash
python monitor_server.py
```

Then open http://localhost:8000 in your browser to see live transfer progress.

---

### Sender Side

#### Step 1: Prepare File

```bash
cd sender/
python chunker_compress_encrypt.py
```

**Enter:**
- File path: `big_video.mp4`
- Priority (1-4): `1` for CRITICAL, `3` for NORMAL

**Output:**
- `echunk_0.bin`, `echunk_1.bin`, ... (encrypted chunks)
- `manifest.json` (metadata)

#### Step 2: Send Files

```bash
python sender_client.py
```

**Enter:**
- Receiver IP: `192.168.1.100` (or `127.0.0.1` for localhost)

**Watch the progress bars!**

---

### Receiver Side

#### Step 1: Start Server

```bash
cd receiver/
python receiver_server.py
```

**Server starts listening on port 5001...**

#### Step 2: Reassemble File

After transfer completes:

```bash
python verify_decrypt_decompress_reassemble.py
```

**Enter:**
- Output filename: `restored_video.mp4`

**Done!** Your file is reconstructed and verified.

---

## ⚙️ Configuration

Edit `config.yaml` to customize system behavior:

```yaml
# Network settings
network:
  port: 5001
  timeout: 30

# Transfer settings
transfer:
  chunk_size_mb: 1
  max_retries: 3
  enable_resume: true

# Priority system
priority:
  enabled: true
  default: 3  # 1=CRITICAL, 2=HIGH, 3=NORMAL, 4=LOW

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "sfts.log"
```

---

## 📊 Priority Levels

| Level | Name | Use Case |
|-------|------|----------|
| 1 | CRITICAL | Emergency medical data, critical alerts |
| 2 | HIGH | Important reports, time-sensitive data |
| 3 | NORMAL | Regular files (default) |
| 4 | LOW | Backups, archives, non-urgent data |

---

## 🔍 How It Works

### Sender Workflow

```
Original File → Split into Chunks → Compress → Encrypt → Send
                      ↓                ↓          ↓        ↓
                   1 MB pieces    30-70% smaller  Locked  TCP/IP
```

### Receiver Workflow

```
Receive → Verify Hash → Decrypt → Decompress → Reassemble
   ↓            ↓          ↓          ↓            ↓
TCP/IP    Check integrity Unlock   Expand    Original File
```

### Resume Example

```
First attempt:
  ✅ manifest.json
  ✅ echunk_0.bin
  ❌ Connection lost!

Second attempt:
  ⏭ Skip manifest.json (already done)
  ⏭ Skip echunk_0.bin (already done)
  ✅ echunk_1.bin ← Resumes here!
  ✅ echunk_2.bin
```

---

## 📁 Project Structure

```
sfts/
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── HOW_IT_WORKS.md         # Detailed beginner's guide
├── monitor_server.py       # Web monitoring dashboard server
│
├── shared/                 # Shared utilities
│   ├── config_loader.py    # Configuration management
│   ├── logger.py           # Logging system
│   └── __init__.py
│
├── sender/                 # Sender components
│   ├── chunker_compress_encrypt.py  # File preparation
│   ├── sender_client.py             # Network transmission
│   ├── sender_status.json           # Live status (generated)
│   └── secret.key                   # Encryption key
│
├── receiver/               # Receiver components
│   ├── receiver_server.py                    # Network reception
│   ├── verify_decrypt_decompress_reassemble.py  # File reconstruction
│   ├── receiver_status.json                  # Live status (generated)
│   └── secret.key                            # Same encryption key
│
└── static/                 # Web dashboard assets
    └── index.html          # Dashboard interface
```

---

## 🎯 Use Cases

### Media Studios

Transfer large video files between editing suites:
- **Priority**: High-res proxies as CRITICAL, raw footage as NORMAL
- **Resume**: Continue overnight transfers if connection drops
- **Compression**: Reduce transfer time for uncompressed formats

### Rural Labs / Clinics

Send medical data over unstable 4G connections:
- **Priority**: Patient records as CRITICAL, administrative files as LOW
- **Encryption**: HIPAA-compliant data protection
- **Resume**: Handle intermittent mobile connections

### Disaster Sites

Emergency data transfer in harsh conditions:
- **Priority**: Emergency coordination data as CRITICAL
- **Resilience**: Automatic retry on satellite link failures
- **Logging**: Audit trail for accountability

### Remote Engineering

CAD files from field sites to factories:
- **Priority**: Design changes as HIGH, documentation as NORMAL
- **Integrity**: SHA256 verification prevents corrupted designs
- **Resume**: Handle VPN disconnections

---

## 📝 Logging

All operations are logged to `sfts.log`:

```
2025-11-16 10:15:23 [INFO] sfts.chunker - Starting chunking process for: big_video.mp4
2025-11-16 10:15:23 [INFO] sfts.chunker - File priority: 1 (CRITICAL)
2025-11-16 10:15:25 [INFO] sfts.chunker - Chunk 0: echunk_0.bin | Raw: 1,048,576 bytes | Compressed: 614,832 bytes (41.4% reduction)
2025-11-16 10:15:30 [INFO] sfts.sender - Connected to receiver at 192.168.1.100:5001
2025-11-16 10:15:35 [INFO] sfts.sender - echunk_0.bin sent successfully on attempt 1
```

Change log level in `config.yaml`:
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages (default)
- `WARNING`: Warning messages
- `ERROR`: Error messages only

---

## 🔒 Security Considerations

### Current Implementation

✅ **Strong encryption**: AES-128 with HMAC
✅ **Integrity verification**: SHA256 hashing
✅ **No plaintext on wire**: All chunks encrypted

⚠ **Limitations**:
- No client authentication
- No TLS for network layer
- Keys stored in plaintext on disk
- Manifest sent unencrypted (metadata leak)

### Recommended for Production

- Add password-based key derivation (PBKDF2)
- Implement mutual TLS authentication
- Encrypt manifest file
- Use hardware security modules (HSM) for key storage
- Add client certificates

---

## 🖥️ Web Monitoring Dashboard

SFTS includes a real-time web monitoring dashboard to track transfer progress.

### Starting the Monitor

```bash
python monitor_server.py
```

The server will start on http://localhost:8000

### Features

- **Real-time Updates**: Refreshes every second
- **Sender Status**: Current file being sent, progress, speed
- **Receiver Status**: Current file being received, verification status
- **File Progress**: Visual progress bars for current file transfer
- **Transfer Statistics**: Files sent/received, total count, errors

### Dashboard Display

The dashboard shows:
- Current transfer state (idle, connecting, sending, receiving, completed)
- Current file name and progress percentage
- File transfer statistics (X / Y files)
- Error messages (if any)
- Live progress bars for visual feedback

**Note**: The sender and receiver automatically update their status to JSON files that the dashboard reads, so no additional configuration is needed.

---

## 🐛 Troubleshooting

### "Connection refused"

**Problem**: Receiver not listening

**Solution**:
```bash
# Check if receiver is running
ps aux | grep receiver_server.py

# Restart receiver
cd receiver/
python receiver_server.py
```

### "Hash mismatch" errors

**Problem**: Chunk corrupted during transfer

**Solution**: Sender automatically retries up to 3 times. If persistent:
- Check network stability
- Verify encryption keys match on both sides
- Check `sfts.log` for detailed error messages

### "File not found: config.yaml"

**Problem**: Configuration file missing

**Solution**:
```bash
# Check if config.yaml exists in project root
ls -la config.yaml

# If missing, check if it's in the correct location
```

### Transfer very slow

**Solutions**:
- Increase `transfer.chunk_size_mb` in `config.yaml` for high-bandwidth links
- Decrease compression level (faster but larger files)
- Check network bandwidth with tools like `iperf3`

---

## 📈 Performance Tips

### For Fast Networks (Gigabit LAN)

```yaml
transfer:
  chunk_size_mb: 4  # Larger chunks
compression:
  level: 3          # Less compression (faster)
```

### For Slow/Unstable Networks (4G, Satellite)

```yaml
transfer:
  chunk_size_mb: 0.5  # Smaller chunks
  max_retries: 5       # More retries
compression:
  level: 9             # Maximum compression
```

---

## 📚 Documentation

- **`README.md`** (this file): Quick start and reference
- **`HOW_IT_WORKS.md`**: Detailed beginner's guide with diagrams
- **`config.yaml`**: Inline comments explaining each setting

---

**Built with ❤️ for reliable file transfers in challenging environments**
