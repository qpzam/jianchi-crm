[中文](README.md)

# JianChi CRM Pro — Shareholder Reduction Intelligent Client Acquisition System

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![AI Powered](https://img.shields.io/badge/AI-Powered-purple.svg)](https://openai.com/)
[![macOS](https://img.shields.io/badge/macOS-Compatible-lightgrey.svg)](https://www.apple.com/macos/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Product Positioning

JianChi CRM Pro is an intelligent client acquisition system designed for block trade institutions and share disposal intermediaries. The system uses AI technology to automatically monitor shareholder reduction plan announcements from China A-share listed companies, extracts key information in real time, and automatically matches contact details — enabling sales teams to reach potential clients at the earliest opportunity.

## 📢 Recent Updates

### v2.3.0 (2026-03-20)
- 🕐 daily_run.sh forces Asia/Shanghai timezone — more reliable date handling under cron
- 🔒 .env file permissions tightened to 600 to prevent credential leakage
- 🛡️ PDF download URL domain validated against cninfo.com.cn before fetching
- 🔍 CNINFO API response structure validation with automatic alerts on field changes
- 💰 Hard daily cap of 100 AI API calls — auto-stops and falls back to regex when exceeded
- 📡 Scraping window expanded to cover prior 2 days + today to catch late-night/weekend announcements
- 📜 Extended disclaimer (investment advice, personal data, outreach compliance)

### v2.2.0 (2026-03-20)
- 📋 Multi-shareholder announcements auto-split into individual records, each retaining its own reduction ratio
- ⏰ Reduction window proximity alert extended to 5 days, with exact countdown in notes
- 🚫 Automatic filtering of correction/supplementary announcements to avoid duplicate data
- 💾 Database backups moved to a dedicated `backups/` directory; `sent_sms.json` switched to atomic writes
- ⚠️ Clear WARNING printed when AI parsing falls back to regex
- 🔔 Cron job failure alert notifications added
- 📜 Disclaimer added to README

### v2.1.0 (2026-03-20)
- 🌟 Venture capital fund auto-detection — automatically flags announcements subject to VC reduction rules
- 🔒 Transferee lock-up auto-determination (no-lock / disputed no-lock / locked) based on share origin + holding ratio
- 🧠 AI-powered smart notes — auto-tags high-ratio, institutional shareholder, window-approaching signals
- 📊 Daily report sorted by lock-up status priority (no-lock items first)

### v2.0.0 (2026-03-17)
- 🤖 Full switch to AI parsing mode — regex retired, accuracy >95%
- 📖 Reduction regulations Q&A module with built-in regulation library + AI answers
- 💬 iMessage SMS + email automated outreach
- ⏰ Scheduled tasks — daily auto-wake + scrape + report generation
- 📇 Full extraction of share origin (no longer simplified)

### v1.0.0 (2026-03-05)
- 📡 Automatic announcement scraping from CNINFO
- 📄 PDF parsing for reduction information extraction
- 📇 Contact database matching

## One-Liner

Every day at 8 AM, automatically scrape A-share reduction announcements → AI-parse PDFs → match phone numbers → generate daily report — reaching clients 2 hours faster than competitors.


## Before & After

| Dimension | Traditional Manual Approach | This System |
|-----------|---------------------------|-------------|
| Announcement Monitoring | Manually browsing CNINFO, WeChat groups — easy to miss | Automatic full-coverage scraping from CNINFO |
| PDF Parsing | Opening and reading each PDF — slow and tedious | AI batch parsing in seconds |
| Contact Lookup | Searching business databases, flipping through address books | Auto-matching from contact database |
| Outreach Efficiency | Manual data entry for SMS and calls | One-click bulk outreach |
| Response Time | 2–4 hours after announcement to make contact | Within 30 minutes of announcement |

---

## Features

| Feature | Description |
|---------|-------------|
| 📈 **Announcement Scraping** | Daily automatic scraping of reduction announcements from CNINFO, with configurable date range |
| 🤖 **AI Parsing** | Supports OpenAI/Claude API for intelligent PDF parsing and key information extraction |
| 📇 **Contact Matching** | Automatic matching against contact database, supporting multiple data formats |
| 📊 **Daily Report** | Auto-generated reports with priority tags and AI-powered smart notes |
| 💬 **Smart Outreach** | Bulk iMessage SMS sending with automatic deduplication |
| ⏰ **Scheduled Execution** | Crontab support with macOS lid-close wake capability |
| 🔍 **CRM Management** | Lead status tracking, follow-up history, conversion funnel analysis |


---

## Quick Start

### One-Click Installation

```bash
# Clone the repository
git clone https://github.com/qpzam/jianchi-crm.git
cd jianchi-crm

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment variable template
cp .env.example .env

# Edit the .env file and add your AI API key
# OPENAI_API_KEY=sk-your-api-key-here
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4
```

Prepare your contact database and place it in the `jianchi/data/` directory:
- Excel format: columns for stock code, stock name, contact person, phone, email, title
- TXT format: `CompanyName ContactPerson Title Phone：138xxxx1234`

### Running

```bash
# Scrape today's announcements (AI mode)
python -m jianchi --mode auto

# Scrape last 7 days
python -m jianchi --days 7 --mode auto

# Generate daily report
python jianchi/gen_daily_report.py

# View dashboard
python -m jianchi dash
```

### Setting Up Scheduled Tasks

```bash
# Edit crontab
crontab -e

# Add daily run at 8:00 AM
0 8 * * * cd /path/to/jianchi-crm && source venv/bin/activate && python -m jianchi --mode auto && python jianchi/gen_daily_report.py

# Configure macOS to stay awake with lid closed (requires admin privileges)
sudo pmset -b disablesleep 0
sudo pmset -b sleep 0  # Prevent sleep on lid close
sudo pmset -b disablesleep 1  # Allow sleep but scheduled tasks will wake the system
```

**⚠️ Note: Choose "sleep on lid close but don't shut down" — scheduled tasks will still auto-wake and run.**

---

## Daily Report Example

```
============================================================
  Shareholder Reduction Daily Report  2026-03-20
  Scraped: 18 | New: 0 | Matched: 15/18
============================================================

🌟 [1] 300567 某芯片公司 (a chip company) | 深圳创新投资合伙企业 (Shenzhen Innovation Investment LP) | 2.80%
    Reduction Method: Block Trade | Reduction Period: 2026-03-25 ~ 2026-09-24
    Share Origin: Acquired pre-IPO
    🌟 VC Fund Reduction | Transferee No-Lock | No ratio restriction | Can be acquired at market price
    ✅ Contact available
    🤖 AI Notes: 🌟 VC fund reduction, no transferee lock-up, no ratio limit — prioritize follow-up
    💚 Transferee No-Lock (VC fund reduction)
    Contacts (1):
      - 赵强 (Zhao Qiang) | 136xxxx7890 | Board Secretary

🔴 [2] 600123 某科技公司 (a tech company) | 创新合伙人 (Innovation Partners) | 3.50%
    Reduction Method: Block Trade | Reduction Period: 2026-03-20 ~ 2026-09-19
    Share Origin: Acquired pre-IPO
    ✅ Contact available
    🤖 AI Notes: High-ratio reduction + likely block trade + institutional shareholder + potential acquisition demand
    🔒 Transferee Locked 6 months (acquired pre-IPO)
    Contacts (2):
      - 王明 (Wang Ming) | 138xxxx1234 | Board Secretary
      - 李华 (Li Hua) | 139xxxx5678 | Securities Representative

🟡 [3] 002456 某制造公司 (a manufacturing company) | 南方资本 (Southern Capital) | 1.80%
    Reduction Method: Centralized Bidding | Reduction Period: 2026-03-25 ~ 2026-09-24
    Share Origin: Secondary market purchase
    ✅ Contact available
    🤖 AI Notes: Institutional shareholder + potential acquisition demand
    💚 Transferee No-Lock (secondary market purchase)
    Contacts (1):
      - 张伟 (Zhang Wei) | 137xxxx9012 | Investment Director

🟢 [4] 300789 某电气公司 (an electrical company) | 苏州高新区 (Suzhou Hi-Tech Zone) | 0.50%
    Reduction Method: Block Trade | Reduction Period: 2026-04-01 ~ 2026-09-30
    Share Origin: Agreement transfer
    ❌ No contact available
    🤖 AI Notes: Routine reduction
    💛 Disputed No-Lock (holding ratio unknown — needs confirmation) (acquired via agreement transfer, holding ratio unknown)

============================================================
  Summary:
    Parsed: 18 → New 0 + Updated 15
    Priority: 🌟VC 1 | 🔴High 3 | 🟡Medium 5 | 🟢Low 6
    VC Fund Reductions: 1 (transferee no-lock)
    Lock-up Assessment: 💚 No-Lock: 5 | 💛 Disputed No-Lock: 3 | 🔒 Locked: 2 | ❓ Pending: 5
    Match Rate: 15/18 (83%)
    Output: jianchi/daily_output/今日减持_20260320.txt
============================================================
```

---

## Outreach Features

### SMS Sending (iMessage)

```bash
# Preview SMS (dry run)
python jianchi/auto_outreach.py sms

# Send SMS
python jianchi/auto_outreach.py sms --send

# Phone follow-up template
python jianchi/auto_outreach.py sms --followup

# Test send
python jianchi/auto_outreach.py test 138xxxx1234
```

### Email Sending

Configure SMTP in `.env`:
```env
SMTP_HOST=smtp.exmail.qq.com
SMTP_PORT=465
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-password
SMTP_FROM=your-name <your-email@example.com>
```

### Outreach Best Practices

| Item | Recommendation |
|------|---------------|
| Timing | Within 30 minutes of announcement, or 9–10 AM |
| Priority Order | 🔴 High-ratio reduction → 🟡 Institutional shareholders → 🟢 Routine reduction |
| Strategy | High-ratio: call first; Medium-ratio: SMS first |
| Frequency | Follow up after 3 days if no response |
| Deduplication | System automatically tracks sent messages to avoid repeat contacts |

---

## Project Structure

```
jianchi-crm/
├── docs/                              # Documentation
│   └── 减持获客系统_操作手册_V2.0.docx
├── jianchi/                           # Core code
│   ├── __init__.py                    # Package init
│   ├── __main__.py                    # Entry point
│   ├── pipeline.py                    # Main pipeline
│   ├── cninfo_fetcher.py             # CNINFO announcement scraper
│   ├── pdf_parser.py                 # PDF parsing (regex + AI)
│   ├── contact_matcher.py            # Contact matching
│   ├── reduction_scorer.py           # Reduction probability scoring
│   ├── auto_outreach.py              # SMS/email outreach
│   ├── gen_daily_report.py           # Daily report generator
│   ├── db.py                         # SQLite database operations
│   ├── cli.py                        # CLI interface
│   ├── config.py                     # Configuration management
│   ├── data/                         # Data directory (not committed)
│   │   ├── contacts_final.txt        # Contact database
│   │   └── contacts_merged.txt       # Merged contacts
│   ├── daily_output/                 # Daily output (not committed)
│   ├── logs/                        # Log directory
│   ├── pdfs/                        # PDF cache (not committed)
│   └── utils/                       # Utility modules
│       ├── __init__.py
│       ├── stock.py                 # Stock-related utilities
│       ├── date_parser.py           # Date parsing
│       └── io.py                    # File I/O utilities
├── daily_run.sh                      # Scheduled task script
├── deploy.sh                         # Deployment script
├── .env.example                      # Environment variable template
├── .gitignore                        # Git ignore config
├── requirements.txt                  # Python dependencies
├── README.md                         # Project description (Chinese)
├── README_EN.md                      # Project description (English)
└── LICENSE                           # MIT License
```

---

## Contact Database Format

### Excel Format

| Stock Code | Stock Name | Contact Person | Phone | Email | Title |
|-----------|-----------|---------------|-------|-------|-------|
| 600123 | 某科技公司 (Tech Co.) | 王明 (Wang Ming) | 138xxxx1234 | wm@example.com | Board Secretary |
| 002456 | 某制造公司 (Mfg Co.) | 李华 (Li Hua) | 139xxxx5678 | lh@example.com | Securities Representative |

### TXT Format

```
某科技公司 王明 董秘 电话：138xxxx1234
某制造公司 李华 证券事务代表 电话：139xxxx5678
某电气公司 张伟 投资总监 电话：137xxxx9012
```

---

## System Requirements

| Component | Requirement |
|-----------|------------|
| OS | macOS 12+ (recommended), Linux (partial feature support) |
| Python | 3.12 or higher |
| AI API | OpenAI API or Claude API |
| Network | Stable internet connection |
| iPhone | Required for SMS via iMessage + iCloud sync (optional) |

---

## Technical Metrics

| Metric | Value |
|--------|-------|
| Scraping Coverage | Full-market reduction announcements from CNINFO |
| Daily Announcements | 10–50 per day |
| AI Parsing Accuracy | >95% (powered by GPT-4/Claude) |
| Contact Database | User-provided; auto-matches board secretary / securities representative contacts |
| Match Rate | 60%–80% (depends on database quality) |
| Processing Time | ~2–5 minutes (for 15 announcements) |

---

## Scheduled Tasks

### Crontab Configuration

```bash
# Run daily at 8:00 AM
0 8 * * * cd ~/Desktop/减持获客系统 && source venv/bin/activate && python -m jianchi --mode auto && python jianchi/gen_daily_report.py

# Run on weekdays only at 8:00 AM
0 8 * * 1-5 cd ~/Desktop/减持获客系统 && source venv/bin/activate && python -m jianchi --mode auto && python jianchi/gen_daily_report.py
```

### macOS Power Management

```bash
# Check current settings
pmset -g

# Prevent sleep on lid close (not recommended — drains battery)
sudo pmset -b sleep 0

# Allow sleep but let scheduled tasks wake the system (recommended)
sudo pmset -b disablesleep 0
sudo pmset -b powernap 1

# Schedule wake
sudo pmset repeat wake MTWRFSU 08:00:00
```

**⚠️ Important: Use "sleep on lid close, don't shut down" mode — the system will auto-wake when a scheduled task fires.**

---

## 📖 Regulation Library

Built-in A-share reduction regulation library with 101 files covering CSRC rules, SSE/SZSE guidelines.

👉 [View full regulation index](docs/REGULATIONS.md)

---

## FAQ

<details>
<summary><b>Q1: What if AI parsing fails?</b></summary>

Check the following:
1. Is `OPENAI_API_KEY` in `.env` correct?
2. Is `OPENAI_BASE_URL` accessible? (A proxy may be needed in mainland China)
3. Is there sufficient API quota?
4. Try switching to `--mode regex` for regex-based parsing as a fallback
</details>

<details>
<summary><b>Q2: Low contact match rate?</b></summary>

1. Verify the contact database format
2. Ensure company names are consistent (remove ST/* prefixes)
3. Try using Excel format — the system auto-detects column names
4. Manually add missing contacts
</details>

<details>
<summary><b>Q3: iMessage SMS sending fails?</b></summary>

1. Confirm macOS and iPhone are on the same iCloud account
2. iPhone Settings → Messages → iMessage → Enable "Text Message Forwarding"
3. Check phone number format (requires +86 prefix)
4. Ensure the Messages app on macOS is signed into iMessage
</details>

<details>
<summary><b>Q4: Scheduled task not running?</b></summary>

1. Check crontab format: `crontab -l`
2. Confirm Python environment path: `which python3`
3. Check cron logs: `log show --predicate 'process == "cron"'`
4. Test whether the command runs manually
</details>

<details>
<summary><b>Q5: How to improve AI parsing accuracy?</b></summary>

1. Use a more capable model (e.g., GPT-4)
2. Adjust the prompt in `pdf_parser.py`
3. Use a dual regex + AI validation mode
4. Manually label error samples for continuous optimization
</details>

<details>
<summary><b>Q6: Is Windows supported?</b></summary>

Core features are supported with limitations:
- ✅ Announcement scraping, PDF parsing, daily report generation
- ✅ Email sending
- ❌ iMessage SMS (not available on Windows)
- ⚠️ Use Windows Task Scheduler instead of crontab for scheduling
</details>

---

## Disclaimer

- This project is for educational and research purposes only and does not constitute investment advice.
- Contact databases are prepared by the user. This project does not provide nor encourage the illegal acquisition of personal information.
- Users must comply with the *Personal Information Protection Law* (PIPL) and all applicable regulations.
- Please use the SMS/email outreach features responsibly and avoid harassment.

---

## License

MIT License — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- [Anthropic](https://claude.com/product/claude-code) - vibe coding
- [CNINFO (巨潮资讯网)](http://www.cninfo.com.cn) - Announcement data source
- [OpenAI](https://openai.com/) - GPT model support
- [pdfplumber](https://github.com/jsvine/pdfplumber) - PDF parsing library


## Contact

Richardclovesmom@163.com

If this project helps you, please give it a ⭐️ Star
