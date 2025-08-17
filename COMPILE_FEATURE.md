# Architecture Mapper - Compile Feature Documentation

## Overview

The Compile feature in Architecture Mapper transforms your visual application architecture into structured prompts that can be used with Generative AI tools to generate code. This bridges the gap between visual design and code implementation.

## Compile Function Features

### 1. **Compile Button**
- Located in the main toolbar
- Opens the Compile Window when clicked
- Only available when at least one function exists in the architecture

### 2. **CompileWindow Interface**
A dedicated window that generates GenAI prompts with the following components:

#### **Compilation Options**
Customizable checkboxes to control what information to include:
- **Include function descriptions**: Adds detailed descriptions for each function
- **Include input/output details**: Lists all inputs and outputs for each function
- **Analyze relationships between functions**: Detects and documents data flow
- **Generate implementation suggestions**: Creates detailed implementation prompts

#### **Generate Prompts Button**
- Regenerates prompts based on current options
- Automatically runs when window opens

### 3. **Intelligent Analysis**

The compile feature performs several types of analysis:

- **Relationship Detection**: Automatically identifies connections between functions by matching outputs to inputs
- **Data Flow Mapping**: Creates a natural language description of how data flows through the system
- **Architecture Summary**: Provides an overview of the entire application structure

### 4. **Generated Prompt Structure**

The system generates comprehensive prompts organized into sections:

#### **Project Overview**
- Application name and summary
- Total number of functions/components
- High-level architecture description

#### **Functions Overview**
For each function, includes:
- Function name
- Description (if provided)
- Input parameters
- Output values
- Position in the architecture

#### **Function Relationships**
- Automatic detection of data flow between functions
- Visual representation in text format (Function A → Function B via "data_name")
- Complete data flow diagram

#### **GenAI Implementation Prompts**

##### 1. Overall Architecture Implementation
```
Create a [Project Name] application with the following architecture:
- Total functions: [number]
- Functions: [list with I/O details]
- Ensure proper data flow between functions and implement error handling.
```

##### 2. Individual Function Implementation Prompts
For each function:
```
Implement a function called '[Function Name]' that:
- Purpose: [description]
- Accepts the following inputs: [input list]
- Validates all inputs appropriately
- Produces the following outputs: [output list]
- Ensures outputs are properly formatted and validated
- Include appropriate error handling and logging.
```

##### 3. Integration Prompt
```
Integrate all the above functions into a cohesive application where:
- Data flows: [detailed flow descriptions]
- Ensure:
  - All functions can communicate as needed
  - Error handling is consistent across the application
  - The application follows best practices for the chosen technology stack
```

##### 4. Testing Prompt
```
Create comprehensive tests for the application including:
- Unit tests for each function
- Integration tests for data flow between functions
- Edge case handling
- Input validation tests
```

### 5. **Export Options**

#### **Copy to Clipboard**
- One-click copy of all generated prompts
- Preserves formatting for easy pasting into AI tools
- Shows success notification

#### **Save to File**
- Export as Markdown (.md) for documentation
- Export as text (.txt) for plain text needs
- Choose custom filename and location
- Preserves all formatting and structure

#### **Live Preview**
- Real-time text area showing generated prompts
- Scrollable view for long architectures
- Monospace font for better readability

## How to Use the Compile Feature

### Step-by-Step Guide

1. **Design Your Architecture**
   - Add functions using the "Add Function" button
   - Double-click functions to add inputs, outputs, and descriptions
   - Arrange functions on the canvas to represent your architecture

2. **Open Compile Window**
   - Click the "Compile" button in the toolbar
   - The Compile Window will open with default options selected

3. **Configure Options**
   - Check/uncheck options based on your needs
   - More options = more detailed prompts
   - Consider your AI tool's context limits when selecting options

4. **Generate Prompts**
   - Click "Generate Prompts" to refresh (auto-generates on open)
   - Review the generated content in the preview area

5. **Export Prompts**
   - Use "Copy to Clipboard" for quick transfer to AI tools
   - Use "Save to File" for documentation or version control

6. **Use with AI Tools**
   - Paste prompts into ChatGPT, Claude, GitHub Copilot, etc.
   - The structured format helps AI understand your requirements
   - Iterate on the generated code based on your specific needs

## Best Practices

### For Optimal Results

1. **Provide Detailed Descriptions**
   - Add clear descriptions to each function
   - Specify the purpose and behavior expected

2. **Define Clear Inputs/Outputs**
   - Use consistent naming conventions
   - Match output names to input names for automatic relationship detection
   - Be specific about data types when possible

3. **Organize Logically**
   - Position related functions near each other
   - Create a visual flow that matches data flow
   - Group functions by subsystem or feature

4. **Review Relationships**
   - Check the detected relationships for accuracy
   - Ensure all intended connections are captured
   - Add matching I/O names to create connections

### Example Use Cases

1. **Web Application Backend**
   - Design API endpoints as functions
   - Show data flow from request to response
   - Generate Express.js or FastAPI code

2. **Data Processing Pipeline**
   - Each transformation as a function
   - Clear data flow from source to destination
   - Generate Python or Node.js pipeline code

3. **Microservices Architecture**
   - Each service as a function group
   - Inter-service communication via I/O matching
   - Generate service definitions and interfaces

4. **Game Systems**
   - Game mechanics as functions
   - State management through I/O
   - Generate game logic implementation

## Technical Details

### Relationship Detection Algorithm
- Iterates through all function pairs
- Matches output names with input names (case-sensitive)
- Creates directed graph of data flow
- Handles multiple connections between same functions

### Prompt Generation Strategy
- Hierarchical structure from overview to details
- Natural language descriptions for clarity
- Code-focused formatting for AI interpretation
- Balanced between human and AI readability

### Integration with Architecture Mapper
- Accesses live function data from canvas
- Respects current project context
- Maintains consistency with saved/loaded projects
- Works with both file and database storage

## Troubleshooting

### Common Issues

1. **No Functions to Compile**
   - Add at least one function before compiling
   - Functions must be on the canvas

2. **Missing Relationships**
   - Check that output and input names match exactly
   - Case-sensitive matching is used
   - Spaces and special characters matter

3. **Prompts Too Long**
   - Disable some options to reduce size
   - Focus on specific subsystems
   - Split large projects into modules

4. **Clipboard Not Working**
   - Some systems may have clipboard restrictions
   - Try saving to file instead
   - Check system permissions

## Future Enhancements

Potential improvements to the compile feature:

1. **Language-Specific Templates**
   - Python, JavaScript, Java templates
   - Framework-specific outputs

2. **Custom Prompt Templates**
   - User-defined prompt structures
   - Save and reuse templates

3. **AI Service Integration**
   - Direct API calls to OpenAI, Anthropic
   - In-app code generation

4. **Relationship Validation**
   - Warn about unconnected functions
   - Suggest potential connections

5. **Code Preview**
   - Show generated code samples
   - Syntax highlighting

## Conclusion

The Compile feature transforms visual architecture design into actionable AI prompts, significantly accelerating the development process. By providing structured, detailed prompts to AI tools, developers can quickly generate boilerplate code, implement complex logic, and maintain consistency across their application architecture.