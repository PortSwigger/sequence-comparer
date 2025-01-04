# SequenceComparer Jython Extension for Burp Suite

## Overview

**SequenceComparer** is a Jython-based extension for Burp Suite that enables advanced comparison of sequences of HTTP requests and their responses. This tool is particularly useful for analyzing differences and similarities between two sets of HTTP sequences.

## Features

### 1. Context Menu Integration
- **Send to "SequenceComparer"**: Select one or multiple requests in Burp Suite's Proxy tab, then send them to SequenceComparer via the context menu.

### 2. Sequence Overview
- Displays sequences in an array format with:
  - A customizable name for each sequence.
  - The number of requests in the sequence.
  - The total length of the responses in the sequence.
  - The sequence order can be reversed.

### 3. Sequence Selection and Display
- Select and display two sequences simultaneously:
  - Requests from each sequence are displayed in separate tables.
  - Facilitates side-by-side analysis.

### 4. Longest Common Subsequence (LCS) Analysis
- Uses a **Dynamic Programming** algorithm to identify the **Longest Common Subsequence (LCS)** of requests between two selected sequences.
- Color-coded request rows:
  - **No color**: Unique to the sequence.
  - **Green**: Common in both sequences, with identical response bodies.
  - **Orange**: Common in both sequences, but response bodies differ.

### 5. Detailed Request/Response View
- Select a request to view its details or response body, depending on the selected mode.
- Leverages a **diff algorithm** for detailed comparison:
  - **Blue**: Deleted content.
  - **Yellow**: Added content.
  - **Orange**: Modified content.

### 6. Scroll Synchronization
- Optional scroll synchronization between the requests/responses of two sequences:
  - Scrolling in one panel mirrors the other.

### 7. Auto-Select Mode
- Enable auto-select mode:
  - Selecting a request in one sequence automatically selects its counterpart in the other sequence (if it exists).

## Installation

1. Download [Jython Standalone](https://central.sonatype.com/artifact/org.python/jython-standalone/versions) and import it on Burp Suite (more details [here](https://portswigger.net/burp/documentation/desktop/extensions/installing-extensions)).
2. Download the `SequenceComparer.py` file.
3. Load it into Burp Suite:
   - Navigate to **Extender** → **Extensions**.
   - Click **Add**, select **Python**, and upload the file.
4. Ensure Jython is configured in Burp Suite for Python extensions.

## Usage

1. Select requests from Burp Suite's HTTP history or repeater.
2. Right-click and choose **Send to SequenceComparer**.
3. Open the **SequenceComparer** tab to analyze sequences:
   - Use the dynamic programming-based LCS analysis for comparisons.
   - Explore detailed differences with the diff algorithm.
   - Adjust settings for scroll synchronization and auto-select mode as needed.

## Screenshots

![Default interface](screenshots/img1.png)

![Used interface](screenshots/img2.png)

- The first screenshot is the interface by default.
- The second screenshot is the interface when used : 
  - Two sequences with default name "New Sequence" (can be changed). The first sequence has 3 requests, the second one 4.
  - Both sequences were selected : on the left are displayed the requests from the first sequence and on the right are displayed the requests from the second sequence.
  - Two common requests were identified : one is displayed in orange because the response's body changed, one is green because the response's body is the same in both sequence.
  - The two orange requests were selected. Then to compare their response "switch between Request/Response mode" was clicked as it displayed the Request's body by default.
  - The changes between the two Responses' body are hilighted on both side in Burp Suite Comparer style. 

## TODOs

- Dark mode compatibility.
- Various ugly things in the code to be cleaned.
- Add contextual menu on requests to send them to another Burp tab.
- Switch to Java to use MontoyaApi (will not happen anytime soon).

## Acknowledgments

Special thanks to SecurityInnovation for their inspirational work on AuthMatrix https://github.com/SecurityInnovation/AuthMatrix