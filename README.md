```markdown




Follow these steps to set up the API for local development:

    Clone the repository:
    Bash

git clone [repository_url]  # Replace with your repository URL
cd [project_directory]     # Navigate into the project directory

Create a virtual environment (recommended):
Bash

python -m venv venv

    Activate the virtual environment:
        On macOS/Linux: source venv/bin/activate
        On Windows: venv\Scripts\activate

Install dependencies:
django
django-rest-framework

Apply database migrations:


python manage.py migrate

Create a superuser (for admin access if needed):


python manage.py createsuperuser

Follow the prompts to create an admin user.

Run the development server:


    python manage.py runserver

    The API server will now be running at http://127.0.0.1:8000/.


Postman is a convenient tool for testing REST APIs. This section explains how to use the provided Postman collection to interact with the Intelligent Scheduling App API.
Importing the Postman Collection

You have been provided with a JSON file containing a Postman Collection definition. To import it into Postman:  

    Open Postman.
    Click on the "Import" button in the top left corner.   

    Choose "Raw text" tab.
    Paste the entire JSON content of the Postman Collection file into the text area.
    Click "Import".

A new collection named "Django Project API Collection" (or similar) will be added to your Postman collections.  



    Authentication:
        POST /auth/register/: Register a new user.
        POST /auth/login/: Log in and obtain session cookies.
    Projects:
        GET /projects/: List all projects (authenticated).
        POST /projects/: Create a new project (authenticated, CSRF protected).
        GET /projects/{project_pk}/schedule/: Get the schedule for a specific project (authenticated).
    Tasks:
        GET /tasks/: List all tasks (authenticated).
        POST /tasks/: Create a new task (authenticated, CSRF protected).
    Task Dependencies:
        POST /task-dependencies/: Create a new task dependency (authenticated, CSRF protected).

