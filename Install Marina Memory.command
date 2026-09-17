#!/bin/bash
# Double-click this file to install Marina Memory. macOS.
# Nothing else is needed: it installs everything, then keeps this window open
# so you can read the result.
cd "$(dirname "$0")" || exit 1

clear
echo "Marina Memory: automatic installer"
echo "This window will show progress. It takes 1 to 3 minutes the first time."
echo ""

bash ./install.sh
status=$?

echo ""
if [ $status -eq 0 ]; then
  echo "Finished. Nothing else to do here."
else
  echo "Something did not work."
  echo "Copy everything in this window (select it with the mouse) and send it to Fadi."
fi
echo ""
read -n 1 -s -r -p "Press any key to close this window."
echo ""
