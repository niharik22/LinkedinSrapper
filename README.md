# LinkedIn Job Scraper

## Why I Chose This Project

LinkedIn is one of the best platforms for finding job opportunities. However, manually browsing through each job listing can be time-consuming and tedious. To make this process more efficient and to gather job-related data for educational purposes, I decided to build a LinkedIn job scraper. This tool allows me to automatically extract job information like job titles, descriptions, locations, and more, saving time and effort.

## What I Did

1. **Project Development**:
   - Built the project using Python.
   - Used Selenium WebDriver for automating interactions with the LinkedIn website.
   - Configured logging to capture detailed logs of the scraping process.
   - Implemented the scraper to extract job data such as titles, descriptions, applicants, and the time since the job was posted.

2. **Dockerized the Application**:
   - Containerized the scraper using Docker to ensure it can run consistently across different environments (local machines, cloud platforms).
   - This allows the project to be deployed on any machine that supports Docker without worrying about setup or dependencies.

## How to Run the Code

### 1. Modify the Script Based on Your Environment

In `src/main/LinkedIn_Scrap.py`, update the file path based on whether you're running the code locally or in Docker:

- **Local**:
  ```python
  with open("../utilities/config.properties.yaml", "r") as file:
  ```

- **Docker**:
  ```python
  with open("/app/utilities/config.properties.yaml", "r") as file:
  ```

### 2. Update Configuration Files

Open `src/utilities/config.properties.yaml` and modify the `env` key:

```yaml
# Options: LOCAL, DOCKER
env: LOCAL   # or DOCKER depending on your environment
```

Depending on your environment, use the appropriate configuration file:
- Local: `config.local.yaml`
- Docker: `config.docker.yaml`

In the configuration file, update your LinkedIn username:

```yaml
username: "abc@gmail.com"  # Replace with your LinkedIn username
```

### 3. Set Password in a Text File

Create a `pass.txt` file containing your LinkedIn password, and then configure its path in the corresponding YAML file.

For Docker, update the path in the config file:
```yaml
password_file: "/app/utilities/pass.txt"
```

### 4. Running the Scraper

**Running Locally:**
1. Install dependencies listed in `requirements.txt` (e.g., selenium, webdriver_manager, pyyaml).
2. Ensure that you have the correct version of chromedriver installed for Selenium.
3. Run the scraper:
   ```
   python src/main/LinkedIn_Scrap.py
   ```

**Running in Docker:**
1. Build the Docker image:
   ```
   docker build -t linkedin-scraper .
   ```
2. Run the Docker container:
   ```
   docker run -v $(pwd)/src/utilities:/app/utilities linkedin-scraper
   ```

## Additional Information

- **Logs**: Logs are generated during the scraping process to capture important information such as login status, number of jobs found, and any errors encountered during scraping. Logs are written both to the console and to a log file as configured in the YAML file.

- **Saving and Loading Data**: Scraped job data is saved as a serialized `.p` file using pickle, making it easy to reload data between scraping sessions. The saved data includes job details such as title, link, location, description, applicants, and time posted.
