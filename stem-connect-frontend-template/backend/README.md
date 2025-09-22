# Simple Backend Template

This is a starter template for a simple backend API server using Python and Flask.

## Getting Started

### Prerequisites

- Python 3.x
- pip

### Installation

1. Clone the repository:
   ```sh
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```sh
   cd stem-connect-backend-template
   ```
3. Create a virtual environment:
   ```sh
   python3 -m venv venv
   ```
4. Activate the virtual environment:
   - On macOS and Linux:
     ```sh
     source venv/bin/activate
     ```
   - On Windows:
     ```sh
     .\venv\Scripts\activate
     ```
5. Install the dependencies:
   ```sh
   pip install -r requirements.txt
   ```

### Development

To start the development server, run:

```sh
python app.py
```

This will start the Flask development server and you can access the API at `http://127.0.0.1:5000`.

### API Endpoints

- `GET /`: Returns a simple "Hello" message.
- `GET /api/message`: Returns a JSON object with a message.
