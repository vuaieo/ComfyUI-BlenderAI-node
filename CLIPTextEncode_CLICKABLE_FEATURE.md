# CLIPTextEncode Clickable Text Feature

## Overview
This feature adds clickable functionality to the individual text items (A, B, C, etc.) in the CLIPTextEncode node's properties panel. Users can now click on any text item to replace it with suggestions from the available word list.

## How It Works

### Before (Original Behavior)
- Text items were displayed as simple labels
- Users had to manually type or use the suggestions list to add new words
- No direct way to replace existing text items

### After (New Behavior)
- Text items are now displayed as clickable buttons with a dropdown arrow icon
- Clicking on any text item opens a popup menu with suggestions from the `mlt_words` collection
- Users can select a replacement word from the menu or cancel the operation

## Usage Instructions

1. **Enable Advanced Text Mode**: 
   - In the CLIPTextEncode node properties panel, click the "OPTIONS" button (gear icon) next to the text field
   - This enables the multiline text interface

2. **View Text Items**:
   - Below the "Suggestions" section, you'll see individual text items (A, B, C, etc.)
   - Each item shows the original text without weight formatting
   - Each item has a dropdown arrow icon indicating it's clickable

3. **Replace Text Items**:
   - Click on any text item (A, B, C, etc.)
   - A popup menu will appear with suggestions from the available word list
   - Select a word from the list to replace the current text item
   - Click "Cancel" to close the menu without making changes

4. **Weight Control**:
   - The weight values (1.00, 1.71, 1.79, etc.) remain editable as before
   - Weight changes are applied to the text items in real-time

## Technical Implementation

### Files Modified
- `SDNode/nodes.py`: Added `ReplaceTextItem` operator and `MLT_REPLACE_WORDS_UL_UIList`
- `SDNode/blueprints.py`: Modified `CLIPTextEncode.draw_button()` method
- `__init__.py`: Added window manager properties for dialog communication

### Key Components
1. **ReplaceTextItem Operator**: Handles the text replacement logic
2. **MLT_REPLACE_WORDS_UL_UIList**: Displays the suggestions in a scrollable list
3. **Window Manager Properties**: Store context information for dialog communication
4. **UI Integration**: Modified the text display to use clickable operators instead of labels

### Features
- **Visual Feedback**: Dropdown arrow icon indicates clickable items
- **Context Preservation**: Maintains text index and property name across menu operations
- **Error Handling**: Graceful handling of invalid indices and missing data
- **Performance**: Limited to 20 suggestions to prevent UI lag
- **Cancel Option**: Users can cancel the replacement operation

## Benefits
- **Improved UX**: Direct replacement of text items without manual typing
- **Consistency**: Uses the same suggestion system as the main interface
- **Efficiency**: Faster text editing workflow
- **Intuitive**: Clear visual indicators for interactive elements

## Compatibility
- Works with existing CLIPTextEncode nodes
- Maintains backward compatibility with saved files
- Integrates seamlessly with the existing multiline text system
