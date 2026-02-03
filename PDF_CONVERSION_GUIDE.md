# How to Convert VIVA_DOCUMENTATION.html to PDF

## Method 1: Browser Print to PDF (Easiest - Recommended)

1. **Open the HTML file:**
   - Double-click `VIVA_DOCUMENTATION.html` to open it in your default browser
   - Or right-click and select "Open with" → Choose your browser (Chrome, Firefox, Edge, etc.)

2. **Print to PDF:**
   - Press `Ctrl + P` (Windows) or `Cmd + P` (Mac)
   - OR Click the browser menu (three dots) → Print

3. **Select PDF as destination:**
   - In the print dialog, choose "Save as PDF" or "Microsoft Print to PDF"
   - Make sure margins are set to "Default" or "Minimum"
   - Click "Save" and choose your location

4. **Result:** Professional PDF document ready for printing or submission!

---

## Method 2: Using Online Converters

1. Visit any HTML to PDF converter:
   - https://html2pdf.com/
   - https://www.ilovepdf.com/html-to-pdf
   - https://www.sejda.com/html-to-pdf

2. Upload `VIVA_DOCUMENTATION.html`

3. Download the converted PDF

---

## Method 3: Using Command Line (Advanced)

### With wkhtmltopdf (if installed):
```bash
wkhtmltopdf VIVA_DOCUMENTATION.html VIVA_DOCUMENTATION.pdf
```

### With Puppeteer (Node.js):
```bash
npm install -g puppeteer
node -e "const puppeteer = require('puppeteer'); (async () => { const browser = await puppeteer.launch(); const page = await browser.newPage(); await page.goto('file://' + __dirname + '/VIVA_DOCUMENTATION.html'); await page.pdf({path: 'VIVA_DOCUMENTATION.pdf', format: 'A4'}); await browser.close(); })();"
```

---

## Tips for Best Results:

- ✅ Use Chrome or Edge for best PDF quality
- ✅ Ensure "Background graphics" is enabled in print settings
- ✅ Set paper size to A4
- ✅ Use "More settings" to adjust margins if needed
- ✅ Preview before saving to check formatting

---

## Quick Print Settings (Chrome/Edge):

1. Open Print dialog (Ctrl+P)
2. Click "More settings"
3. Set:
   - Paper size: A4
   - Margins: Default
   - Scale: 100%
   - ✅ Background graphics: Enabled
4. Save as PDF


