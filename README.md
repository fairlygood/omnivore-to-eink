# Readeck PDF Exporter

This is a simple flask application that connects to a self-hosted Readeck API, retrieves a bunch of your articles and converts them to a PDF suitable for reading on large format eReaders.

Features:

- PDF output is sized approriately for most large e-ink devices
- Uses Ghostscript to compress PDF output, reducing device storage requirments and bandwidth
- Navigable table of contents
- Optional two-column view
- Images included
- Download most recent or oldest articles, or build a custom document

It should be trivial to host this on your own hardware.

A hosted version is available [here](https://readeck-pdf.fairlygood.net).

## Installation

1. Clone the repository
2. Create a virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Run the server: `./start-server.sh`

