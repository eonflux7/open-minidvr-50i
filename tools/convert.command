#!/bin/sh
# macOS: double-click to convert Mini DVR recordings (a file dialog opens; see convert.sh).
# The first time, macOS may refuse to open it because it was downloaded: right-click it, choose Open, then Open again.
exec /bin/sh "$(dirname "$0")/convert.sh" "$@"
