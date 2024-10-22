# Omnivore to E-Ink

This is a simple flask application that connects to the Omnivore API, retrieves a bunch of your articles and converts them to a PDF suitable for reading on large format eReaders, or an ePub for others.

Features:

- PDF output is sized approriately for most large e-ink devices
- Uses Ghostscript to compress PDF output, reducing device storage requirments and bandwidth
- Navigable table of contents
- Optional two-column view (PDF only)
- Images included
- Download most recent or oldest articles, or build a custom document
- Option to mark as read on Omnivore

It should be trivial to host this on your own hardware.

A hosted version is available [here](https://omnivore-to-eink.fairlygood.net).

## Installation

1. Clone the repository
2. Create a virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Run the server: `./start-server.sh`

