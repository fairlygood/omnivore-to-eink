# Omnivore to PDF

This is a simple flask application that connects to the Omnivore API, retrieves a bunch of your articles and converts them to a PDF suitable for reading on large format eReaders, like the Remarkable or Kindle Scribe. It's mainly useful for devices that can't use the official Omnivore app, or if you want to mark-up the documents.

Features:

- Output is sized approriately for most large e-ink devices
- Uses Ghostscript to compress the output, reducing device storage requirments and bandwidth
- Navigable table of contents
- Images included
- Filter by label
- Option to mark as read on Omnivore

It should be trivial to host this on your own hardware.

A hosted version is available [here](https://omnivore-to-pdf.fairlygood.net).

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Edit config.py with your URL
4. Run the server: `python start-server.sh`

