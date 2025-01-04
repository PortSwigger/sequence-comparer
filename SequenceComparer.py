from burp import IBurpExtender, ITab, IContextMenuFactory
from javax.swing import JPanel, JLabel, JTable, JScrollPane, JSplitPane, JTabbedPane, JMenuItem, JButton, JCheckBox, ListSelectionModel, JTextArea, Timer, BoxLayout
from javax.swing.border import MatteBorder
from javax.swing.table import DefaultTableModel, DefaultTableCellRenderer
from javax.swing.text import DefaultHighlighter
from java.awt import BorderLayout, Color, Component
from java.awt.event import ActionListener
from difflib import Differ
import re


class ReqTableModel(DefaultTableModel):
    # Custome JTable model to set row colors 
    def __init__(self, columnNames, rowCount):
        super(ReqTableModel, self).__init__()
        # Initialize row colors info
        self.rowColors = {}
        self.setColumnIdentifiers(columnNames)

    def setRowColor(self, row, c):
        # Update the row color and refresh table row
        self.rowColors[row] = c
        self.fireTableRowsUpdated(row, row)

    def getRowColor(self, row):
        # Return color if defined, default is No color
        if row in self.rowColors:
            return self.rowColors[row]
        else:
            return None

    def clearRowColors(self):
        self.rowColors = {}

    def getColumnClass(self, column):
        return str

    def isCellEditable(self, row, column):
        return False


class ReqTableCellRenderer(DefaultTableCellRenderer):
    # Custom Cell Renderer to set row colors
    def getTableCellRendererComponent(self, table, value, isSelected, hasFocus, row, column):
        # Get the model and component to render
        model = table.getModel()
        component = super(ReqTableCellRenderer, self).getTableCellRendererComponent(
            table, value, isSelected, hasFocus, row, column
        )
        # Set the background color based on the model's row color
        if(isSelected):
            component.setBorder(MatteBorder(2, 0, 2, 0, Color(0xb5bedb)))
        else:
            component.setBorder(MatteBorder(2, 0, 2, 0, model.getRowColor(row)))
        component.setBackground(model.getRowColor(row))
        return component


class BurpExtender(IBurpExtender, ITab, IContextMenuFactory):

    ############
    ## Layout ##
    ############

    def initColumnsWidth(self, table, column_widths, type):
        # This function looks ugly ? Yes. TODO : find a way to call it after it is drawn so that the table width is retrievable
        table_width = 1000
        if type:
            table_width = 500
        for index, width_fraction in enumerate(column_widths):
            preferred_width = int(round(table_width * width_fraction))
            min_width = len(table.getColumnModel().getColumn(index).getHeaderValue())*10
            table.getColumnModel().getColumn(index).setPreferredWidth(preferred_width)
            table.getColumnModel().getColumn(index).setMinWidth(min_width)


    def registerExtenderCallbacks(self, callbacks):
        # Burp stuff
        self.callbacks = callbacks
        self.helpers = callbacks.getHelpers()
        self.callbacks.setExtensionName("SequenceComparer")

        # Initialize main panel
        self.main_panel = JPanel(BorderLayout())

        # Sequences table setup
        self.setupSequenceOverviewPanel()

        # Buttons creation
        self.setupActionButtons()

        # Request tables and Request/Response editor setup
        self.setupRequestPanels()

        # Color Legend Panel
        self.setupColorLegendPanel()

        # Initialize Comparison split panes
        self.setupComparisonPanels()

        # Merging everything into a main panel
        self.mergePanels()

        # Initialize sequence data and state variables
        self.initializeVariables()


        # Resize the bottom horizontal split after init, is this ugly ? yes
        # Todo : find how to get a callback when the ui is fully drawn to update the split

        main_split_pane = self.main_split_pane

        class resizeBottomSplit(ActionListener):
            def actionPerformed(self, e):
                main_split_pane.setDividerLocation(main_split_pane.getSize().height / 2)

        timer = Timer(500, resizeBottomSplit())
        timer.setRepeats(False)
        timer.start()


        # Register context menu and add suite tab
        callbacks.registerContextMenuFactory(self)
        callbacks.addSuiteTab(self)


    def setupSequenceOverviewPanel(self):
        # Sequences table
        self.sequence_table_model = DefaultTableModel(
            ["ID", "Name", "Req. Count", "1st URL", "1st St. Code", "Last URL", "Last St. Code", "Tot. Len."], 0
        )
        seq_table_column_widths = [0, 0.20, 0, 0.40, 0, 0.40, 0, 0]
        self.sequence_table = JTable(self.sequence_table_model)
        self.sequence_table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        self.sequence_table_scroll = JScrollPane(self.sequence_table)
        self.initColumnsWidth(self.sequence_table, seq_table_column_widths, 0)


    def setupActionButtons(self):
        # Buttons & toggles panel
        self.action_buttons_panel = JPanel()

        buttons = [
            ("Select as First Sequence", self.selectFirstSequence),
            ("Select as Second Sequence", self.selectSecondSequence),
            ("Reverse selected Sequence order", self.reverseSequenceOrder),
            ("Delete Sequence", self.deleteSequence),
            ("Clear Req panels", self.clearPanels),
            ("Switch between Request/Response Mode", self.toggleRequestResponse)
        ]
        for text, action in buttons:
            self.action_buttons_panel.add(JButton(text, actionPerformed=action))

        # Toggles
        self.sync_toggle = JCheckBox("Sync Left/Right selection", actionPerformed=self.toggleSyncMode)
        self.sync_scroll_toggle = JCheckBox("Sync Left/Right scroll", actionPerformed=self.toggleSyncScrollMode)
        self.action_buttons_panel.add(self.sync_toggle)
        self.action_buttons_panel.add(self.sync_scroll_toggle)


    def setupRequestPanels(self):
        # Left and right request/response panels

        self.first_sequence_table_model = ReqTableModel(["ID", "Method", "Host", "URL", "St. Code", "Length"], 0)
        self.first_sequence_table = self.createRequestTable(self.first_sequence_table_model, self.displayFirstRequestResponse)
        self.first_sequence_scroll = JScrollPane(self.first_sequence_table)

        self.second_sequence_table_model = ReqTableModel(["ID", "Method", "Host", "URL", "St. Code", "Length"], 0)
        self.second_sequence_table = self.createRequestTable(self.second_sequence_table_model, self.displaySecondRequestResponse)
        self.second_sequence_scroll = JScrollPane(self.second_sequence_table)

        self.request_selector_split_pane = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, self.first_sequence_scroll, self.second_sequence_scroll)
        

    def setupColorLegendPanel(self):
        # Colors legend
        # This is ugly
        def HighlightLabel(label, color):
            label.setBackground(color)
            label.setOpaque(True)
            return label

        Green, Blue, Yellow, Orange = Color(0xb5ffa1), Color(0x97c8f6), Color(0xf1f499), Color(0xffd786)

        # First legend
        self.legend_request_panel = JPanel()
        self.legend_request_panel.setLayout(BoxLayout(self.legend_request_panel, BoxLayout.X_AXIS))

        legend_request_panel_labels = [
            JLabel("Requests color code : "),
            HighlightLabel(JLabel("Same Response"), Green),
            JLabel(" | "),
            HighlightLabel(JLabel("Different Response"), Orange)
        ]

        for lab in legend_request_panel_labels:
            self.legend_request_panel.add(lab)

        # Second legend
        self.legend_comparison_panel = JPanel()
        self.legend_comparison_panel.setLayout(BoxLayout(self.legend_comparison_panel, BoxLayout.X_AXIS))

        legend_comparison_panel_labels = [ 
            JLabel("Comparer color code : "),
            HighlightLabel(JLabel("Modified"), Orange),
            JLabel(" | "),
            HighlightLabel(JLabel("Deleted"), Blue),            
            JLabel(" | "),
            HighlightLabel(JLabel("Added"), Yellow)
        ]

        for lab in legend_comparison_panel_labels:
            self.legend_comparison_panel.add(lab)


    def setupComparisonPanels(self):
        # Comparison layout
        self.first_request_response_editor = self.createRequestResponseEditor()
        self.first_request_response_editor_scroll = JScrollPane(self.first_request_response_editor)

        self.second_request_response_editor = self.createRequestResponseEditor()
        self.second_request_response_editor_scroll = JScrollPane(self.second_request_response_editor)

        self.first_request_response_panel = JPanel(BorderLayout())
        self.first_request_response_panel.add(self.first_request_response_editor_scroll, BorderLayout.CENTER)

        self.second_request_response_panel = JPanel(BorderLayout())
        self.second_request_response_panel.add(self.second_request_response_editor_scroll, BorderLayout.CENTER)

        self.request_response_split_pane = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, self.first_request_response_panel, self.second_request_response_panel)
        

    def mergePanels(self):
        # merge sequence selector and buttons
        self.sequence_overview_panel = JPanel(BorderLayout())
        self.sequence_overview_panel.add(self.sequence_table_scroll)
        self.sequence_overview_panel.add(self.action_buttons_panel, BorderLayout.SOUTH)

        # Add Color legend to request selector
        self.req_and_legend = JPanel()
        self.req_and_legend.setLayout(BoxLayout(self.req_and_legend, BoxLayout.Y_AXIS))
        self.request_selector_split_pane.setAlignmentX(Component.CENTER_ALIGNMENT)
        self.req_and_legend.add(self.request_selector_split_pane)
        self.req_and_legend.add(self.legend_request_panel)
        self.req_and_legend.add(self.legend_comparison_panel)

        # merge request selectors+color legend and comparison panels
        self.main_split_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, self.req_and_legend, self.request_response_split_pane)

        # merge Seq+button and Select+Compar
        self.overall_split_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, self.sequence_overview_panel, self.main_split_pane)

        self.request_selector_split_pane.setResizeWeight(0.5)
        self.request_response_split_pane.setResizeWeight(0.5)
        self.main_split_pane.setResizeWeight(0.5)
        self.overall_split_pane.setResizeWeight(0.25)

        #add everything to the main panel
        self.main_panel.add(self.overall_split_pane, BorderLayout.CENTER)


    def createRequestTable(self, model, selection_listener):
        table = JTable(model)
        table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        table.getSelectionModel().addListSelectionListener(selection_listener)
        table.setDefaultRenderer(str, ReqTableCellRenderer())
        req_table_column_widths = [0, 0, 0.25, 0.62, 0, 0]
        self.initColumnsWidth(table, req_table_column_widths, 1)
        return table


    def createRequestResponseEditor(self):
        editor = JTextArea()
        editor.setEditable(False)
        editor.setLineWrap(True)
        return editor


    def initializeVariables(self):
        self.sequence_data = []
        self.display_request = True
        self.sync_mode = False
        self.sync_scroll_mode = False
        self.first_scroll_save = self.first_request_response_editor_scroll.getVerticalScrollBar().getModel()
        self.second_scroll_save = self.second_request_response_editor_scroll.getVerticalScrollBar().getModel()
        self.sync_scroll_unselected = False
        self.sync_biggest_common_sequence = []
        self.first_request_response_sequence_id = -1
        self.second_request_response_sequence_id = -1



    ###################################
    ## Extension integration in Burp ##
    ###################################

    def getTabCaption(self):
        return "SequenceComparer"


    def getUiComponent(self):
        return self.main_panel


    def highlightTab(self):
        # Thanks to SecurityInnovation/AuthMatrix for the function
        currentPane = self.main_panel
        previousPane = None 

        breaker = 100 
        while currentPane and not isinstance(currentPane, JTabbedPane) and breaker:
            previousPane = currentPane
            currentPane = currentPane.getParent()
            breaker -= 1

        if currentPane:
            index = currentPane.indexOfComponent(previousPane)
            currentPane.setBackgroundAt(index, Color(0xff6633))

            class setColorBackActionListener(ActionListener):
                def actionPerformed(self, e):
                    currentPane.setBackgroundAt(index, None)

            timer = Timer(1000, setColorBackActionListener())
            timer.setRepeats(False)
            timer.start()


    def createMenuItems(self, invocation):
        menu_item = JMenuItem("Send Sequence to SequenceComparer", actionPerformed=lambda x: self.handleMenuAction(invocation))
        return [menu_item]


    def handleMenuAction(self, invocation):
        selected_messages = invocation.getSelectedMessages()
        if selected_messages:
            self.addSequence(selected_messages)
            self.highlightTab()



    ###############
    ## The Stuff ##
    ###############

    # Buttons

    def selectFirstSequence(self, event):
        sequence_id = self.sequence_table.getSelectedRow()
        if sequence_id != -1:
            self.populateTable(self.first_sequence_table_model, self.sequence_data[sequence_id])
            self.first_request_response_sequence_id = sequence_id
            self.displayFirstRequestResponse(0)
            self.refreshBiggestCommonSequence()
            self.SyncScrolls()


    def selectSecondSequence(self, event):
        sequence_id = self.sequence_table.getSelectedRow()
        if sequence_id != -1:
            self.populateTable(self.second_sequence_table_model, self.sequence_data[sequence_id])
            self.second_request_response_sequence_id = sequence_id
            self.displaySecondRequestResponse(0)
            self.refreshBiggestCommonSequence()
            self.SyncScrolls()


    def reverseSequenceOrder(self, event):
        selected_row = self.sequence_table.getSelectedRow()
        if selected_row != -1:
            self.sequence_data[selected_row] = self.sequence_data[selected_row][::-1]
            
            # inverse first/last url and first/last status code from the sequences table
            last_url = self.sequence_table_model.getValueAt(selected_row, 5)
            last_status_code = self.sequence_table_model.getValueAt(selected_row, 6)

            self.sequence_table_model.setValueAt(self.sequence_table_model.getValueAt(selected_row, 3), selected_row, 5)
            self.sequence_table_model.setValueAt(self.sequence_table_model.getValueAt(selected_row, 4), selected_row, 6)
            self.sequence_table_model.setValueAt(last_url, selected_row, 3)
            self.sequence_table_model.setValueAt(last_status_code, selected_row, 4)

            if selected_row == self.first_request_response_sequence_id:
                self.selectFirstSequence(0)
            if selected_row == self.second_request_response_sequence_id:
                self.selectSecondSequence(0)   

            self.refreshBiggestCommonSequence() 


    def deleteSequence(self, event):
        selected_row = self.sequence_table.getSelectedRow()
        if selected_row != -1:
            self.clearPanels(0)
            self.sequence_data.pop(selected_row)
            self.sequence_table_model.removeRow(selected_row)


    def clearPanels(self, event):
        self.first_sequence_table_model.setRowCount(0)
        self.second_sequence_table_model.setRowCount(0)
        self.first_request_response_editor.replaceRange("", 0, self.first_request_response_editor.getRows())
        self.second_request_response_editor.replaceRange("", 0, self.second_request_response_editor.getRows())
        self.first_request_response_sequence_id = -1
        self.second_request_response_sequence_id = -1


    def toggleRequestResponse(self, event):
        self.display_request = not self.display_request  # Toggle display flag
        self.displayFirstRequestResponse(None)  # Refresh display
        self.displaySecondRequestResponse(None)  # Refresh display


    def toggleSyncMode(self, event):
        self.sync_mode = self.sync_toggle.isSelected()
        if self.sync_mode:
            self.refreshBiggestCommonSequence()


    def toggleSyncScrollMode(self, event):
        self.sync_scroll_mode = self.sync_scroll_toggle.isSelected()
        if not self.sync_scroll_mode:
            self.sync_scroll_unselected = True
        self.SyncScrolls()


    # Sequence

    def addSequence(self, messages):
        sequence_id = len(self.sequence_data) + 1

        # Sequence details
        name = "New Sequence"
        num_requests = len(messages)

        # Calculate total length of requests and responses
        total_length = sum(
            len(msg.getRequest()) + (len(msg.getResponse()) if msg.getResponse() else 0)
            for msg in messages
        )

        # Extract first and last request details
        first_request, last_request = messages[0], messages[-1]

        analyze = self.helpers.analyzeRequest
        first_url = analyze(first_request).getUrl().toString()
        last_url = analyze(last_request).getUrl().toString()

        analyze_response = self.helpers.analyzeResponse
        first_status_code = (
            analyze_response(first_request.getResponse()).getStatusCode()
            if first_request.getResponse()
            else "N/A"
        )
        last_status_code = (
            analyze_response(last_request.getResponse()).getStatusCode()
            if last_request.getResponse()
            else "N/A"
        )

        # Add row to sequence table model
        self.sequence_table_model.addRow([
            sequence_id, name, num_requests, first_url, first_status_code, last_url, last_status_code, total_length
        ])

        # Store messages in sequence data
        self.sequence_data.append(messages)


    def findBiggestCommonSequence(self, seq1, seq2):

        # Longest Common Subsequence (LCS) problem.
        # It returns the IDs of the elements from both Sequences that forms the longest common Sequence

        def sum_of_differences(indices):
            return sum(indices[i + 1][1] - indices[i][1] for i in range(len(indices) - 1))

        # Dynamic Programming Table
        n1, n2 = len(seq1), len(seq2)
        dp = [[[] for _ in range(n2 + 1)] for _ in range(n1 + 1)]

        for i in range(1, n1 + 1):
            for j in range(1, n2 + 1):
                if seq1[i - 1] == seq2[j - 1]:
                    # If there's a match, extend the sequence
                    dp[i][j] = dp[i - 1][j - 1] + [(i - 1, j - 1)]
                else:
                    # Otherwise, take the longer sequence from previous states
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1], key=len)

        # Find the best sequence
        best_mapping = max(dp[-1], key=lambda x: (len(x), sum_of_differences(x)))
        return best_mapping


    def refreshBiggestCommonSequence(self):
        # getting the biggest sub sequence
        seq1 = [self.first_sequence_table_model.getValueAt(obj, 3) for obj in range(self.first_sequence_table_model.getRowCount())]
        seq2 = [self.second_sequence_table_model.getValueAt(obj, 3) for obj in range(self.second_sequence_table_model.getRowCount())]
        self.sync_biggest_common_sequence = self.findBiggestCommonSequence(seq1, seq2)  

        self.first_sequence_table_model.clearRowColors()
        self.second_sequence_table_model.clearRowColors()

        for first, second in self.sync_biggest_common_sequence:
            left_response = self.sequence_data[self.first_request_response_sequence_id][first].getResponse()
            right_response = self.sequence_data[self.second_request_response_sequence_id][second].getResponse()

            left_body_offset, right_body_offset = 0, 0
            left_body, right_body = "", ""
            if left_response != None:
                left_body_offset = self.helpers.analyzeResponse(left_response).getBodyOffset()
                left_body = self.helpers.bytesToString(left_response)[left_body_offset:]
            if right_response != None:
                right_body_offset = self.helpers.analyzeResponse(right_response).getBodyOffset()
                right_body = self.helpers.bytesToString(right_response)[right_body_offset:]

            if left_body == right_body:
                self.first_sequence_table_model.setRowColor(first, Color(0xb5ffa1))
                self.second_sequence_table_model.setRowColor(second, Color(0xb5ffa1))
            else:
                self.first_sequence_table_model.setRowColor(first, Color(0xffd786))
                self.second_sequence_table_model.setRowColor(second, Color(0xffd786))               


    # Requests/Responses

    def populateTable(self, model, messages):
        model.setRowCount(0)  # Clear existing rows
        for idx, message in enumerate(messages):
            request_info = self.helpers.analyzeRequest(message)
            host = message.getHttpService().getHost()
            method = request_info.getMethod()
            url = request_info.getUrl().toString()
            status_code = self.helpers.analyzeResponse(message.getResponse()).getStatusCode() if message.getResponse() else "N/A"
            length = len(message.getRequest()) + (len(message.getResponse()) if message.getResponse() else 0)
            model.addRow([idx + 1, method, host, url, status_code, length])


    def syncSelection(self, request_id, target):
        bs = self.sync_biggest_common_sequence
        if target == "first":
            match = [first for first, second in bs if second == request_id]
            if match != []:
                self.first_sequence_table.setRowSelectionInterval(match[0], match[0])
        else:
            match = [second for first, second in bs if first == request_id]
            if match != []:
                self.second_sequence_table.setRowSelectionInterval(match[0], match[0])


    # Comparer 

    def setTextWithHighlight(self, text_area, text, highlights):
        text = "".join(text)
        text_area.setText(text)
        highlighter = text_area.getHighlighter()

        highlighter.removeAllHighlights()

        for highlight in highlights:
            text_area.getHighlighter().addHighlight(highlight["start"], highlight["end"], DefaultHighlighter.DefaultHighlightPainter(highlight["color"]))
        text_area.setCaretPosition(0)


    def compareMessages(self, message1, message2):
        # Retrieve message
        response1 = self.helpers.bytesToString(
            self.helpers.bytesToString(message1.getRequest()) if self.display_request else self.helpers.bytesToString(message1.getResponse())
        )
        response2 = self.helpers.bytesToString(
            self.helpers.bytesToString(message2.getRequest()) if self.display_request else self.helpers.bytesToString(message2.getResponse())
        )

        if response1 == None:
            response1 = ""
        if response2 == None:
            response2 = ""

        # Perform comparison
        diff = list(Differ().compare(response1.splitlines(), response2.splitlines()))

        left_text, right_text = [], []
        left_text_highlights, right_text_highlights = [], []
        left_line_index, right_line_index = 0, 0
        Blue, Yellow, Orange = Color(0x97c8f6), Color(0xf1f499), Color(0xffd786)

        for index, line in enumerate(diff):
            text = line[2:] + "\n"
            if line.startswith(" "):  # Unchanged lines
                left_text.append(text)
                left_line_index += len(text)
                right_text.append(text)
                right_line_index += len(text)

            elif line.startswith("-"):  # Deletions
                left_text.append(text)
                left_text_highlights.append({"start": left_line_index, "end": left_line_index + len(text), "color": Blue})
                left_line_index += len(text)

            elif line.startswith("+"):  # Additions
                right_text.append(text)
                right_text_highlights.append({"start": right_line_index, "end": right_line_index + len(text), "color": Yellow})
                right_line_index += len(text)

            elif line.startswith("?"):  # Modifications
                is_left = diff[index-1].startswith("-")
                if is_left:
                    left_text_highlights.pop()
                    left_line_index -= len(diff[index-1][2:] + "\n")
                else:
                    right_text_highlights.pop()
                    right_line_index -= len(diff[index-1][2:] + "\n")

                for match in re.finditer(r"[;+\-^]+", text):
                    start = match.start()
                    end = match.end()
                    # Deletion part
                    if is_left:
                        left_text_highlights.append({"start": left_line_index + start, "end": left_line_index + end, "color": Orange})
                    # Addition part
                    elif diff[index-1].startswith("+"):  
                        right_text_highlights.append({"start": right_line_index + start, "end": right_line_index + end, "color": Orange})

                if is_left:
                    left_line_index += len(diff[index-1][2:] + "\n")
                else:
                    right_line_index += len(diff[index-1][2:] + "\n")



        # Set text and highlight
        self.setTextWithHighlight(self.first_request_response_editor, left_text, left_text_highlights)
        self.setTextWithHighlight(self.second_request_response_editor, right_text, right_text_highlights)


    def displayFirstRequestResponse(self, event):
        selected_row = self.first_sequence_table.getSelectedRow()
        if selected_row != -1:
            sequence_index = self.first_request_response_sequence_id
            message = self.sequence_data[sequence_index][selected_row]
            if self.display_request:
                self.first_request_response_editor.setText(self.helpers.bytesToString(message.getRequest()))
                self.first_request_response_editor.setCaretPosition(0)
            elif message.getResponse() is not None:
                self.first_request_response_editor.setText(self.helpers.bytesToString(message.getResponse()))
                self.first_request_response_editor.setCaretPosition(0)
            else:
                self.first_request_response_editor.setText("")
                self.first_request_response_editor.setCaretPosition(0)

            if self.sync_mode:
                self.syncSelection(selected_row, "second")
        else:
            self.first_request_response_editor.setText("")
            self.first_request_response_editor.setCaretPosition(0)

        left_selected_row = self.first_sequence_table.getSelectedRow()
        right_selected_row = self.second_sequence_table.getSelectedRow()

        if left_selected_row != -1 and right_selected_row != -1:
            left_sequence_index = self.first_request_response_sequence_id
            right_sequence_index = self.second_request_response_sequence_id

            message1 = self.sequence_data[left_sequence_index][left_selected_row]
            message2 = self.sequence_data[right_sequence_index][right_selected_row] 
            self.compareMessages(message1, message2)

            self.SyncScrolls()


    def displaySecondRequestResponse(self, event):
        selected_row = self.second_sequence_table.getSelectedRow()
        if selected_row != -1:
            sequence_index = self.second_request_response_sequence_id
            message = self.sequence_data[sequence_index][selected_row]
            if self.display_request:
               self.second_request_response_editor.setText(self.helpers.bytesToString(message.getRequest()))
               self.second_request_response_editor.setCaretPosition(0)
            elif message.getResponse() is not None:
                self.second_request_response_editor.setText(self.helpers.bytesToString(message.getResponse()))
                self.second_request_response_editor.setCaretPosition(0)
            else:
                self.second_request_response_editor.setText("")
                self.second_request_response_editor.setCaretPosition(0)

            if self.sync_mode:
                self.syncSelection(selected_row, "first")
        else:
            self.second_request_response_editor.setText("")
            self.second_request_response_editor.setCaretPosition(0)

        left_selected_row = self.first_sequence_table.getSelectedRow()
        right_selected_row = self.second_sequence_table.getSelectedRow()

        if left_selected_row != -1 and right_selected_row != -1:
            left_sequence_index = self.first_request_response_sequence_id
            right_sequence_index = self.second_request_response_sequence_id

            message1 = self.sequence_data[left_sequence_index][left_selected_row]
            message2 = self.sequence_data[right_sequence_index][right_selected_row] 
            self.compareMessages(message1, message2)

            self.SyncScrolls()
  

    def SyncScrolls(self):
        if self.sync_scroll_mode:
            if len(self.first_request_response_editor.getText()) and len(self.second_request_response_editor.getText()) :
                if len(self.first_request_response_editor.getText()) > len(self.second_request_response_editor.getText()):
                    self.second_request_response_editor_scroll.getVerticalScrollBar().setModel(self.first_request_response_editor_scroll.getVerticalScrollBar().getModel())
                else :
                    self.first_request_response_editor_scroll.getVerticalScrollBar().setModel(self.second_request_response_editor_scroll.getVerticalScrollBar().getModel())
            else:
                self.first_request_response_editor_scroll.getVerticalScrollBar().setModel(self.first_scroll_save)
                self.second_request_response_editor_scroll.getVerticalScrollBar().setModel(self.second_scroll_save) 
            self.first_request_response_editor.setCaretPosition(0)
            self.second_request_response_editor.setCaretPosition(0) 
        else:
            if self.sync_scroll_unselected: 
                self.first_request_response_editor_scroll.getVerticalScrollBar().setModel(self.first_scroll_save)
                self.second_request_response_editor_scroll.getVerticalScrollBar().setModel(self.second_scroll_save) 
                self.first_request_response_editor.setCaretPosition(0)
                self.second_request_response_editor.setCaretPosition(0)  
                self.sync_scroll_unselected = False
