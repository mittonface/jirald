# JIRA Card Creation GitHub App

A GitHub App that creates JIRA cards using natural language through AWS Bedrock, with automated card creation from PR context when mentioned in comments.

## What It Does

**Creates JIRA cards from PR context** when you mention the bot in pull request comments. The bot analyzes the PR details and your request to generate appropriate JIRA issues automatically.

## Project Structure

### Core Files
- `github_app.py` - Main GitHub App for PR-based JIRA card creation
- `jira_client.py` - JIRA client for creating issues
- `config.py` - Centralized configuration management
- `services.py` - Service classes for GitHub, Bedrock, and prompt handling

### Configuration
- `.env` - Your JIRA, AWS, and GitHub credentials

## Setup

### 1. Install Dependencies

```bash
uv sync
source .venv/bin/activate
```

### 2. Configure Credentials

Create a `.env` file with:

```bash
# JIRA Configuration
JIRA_URL=https://yourcompany.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token

# AWS Configuration
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret

# GitHub App Configuration
GITHUB_APP_ID=your_app_id_here
GITHUB_PRIVATE_KEY=your_base64_encoded_private_key
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
```

## Usage

### Step 1: Create GitHub App

1. **Go to GitHub Settings**:
   - Personal account: `https://github.com/settings/apps`
   - Organization: `https://github.com/organizations/YOUR_ORG/settings/apps`

2. **Click "New GitHub App"**

3. **Configure Basic Information**:
   - **App name**: `JIRA Card Creator`
   - **Description**: `Creates JIRA cards from PR context when tagged`
   - **Homepage URL**: `https://your-domain.com`
   - **Webhook URL**: `https://your-server.com/webhook`
   - **Webhook secret**: Generate a strong secret and save it

4. **Set Permissions**:
   - **Repository permissions**:
     - Pull requests: `Read & Write`
     - Issues: `Read & Write` 
     - Contents: `Read`
     - Metadata: `Read`
   - **Subscribe to events**:
     - [x] Issue comments
     - [x] Pull requests

5. **Create the app** and note down:
   - **App ID** (add to `.env`)
   - **Download the private key** (base64 encode and add to `.env`)

### Step 2: Install the App on Repository

1. **Go to your GitHub App page**:
   - `https://github.com/settings/apps/YOUR_APP_NAME`

2. **Click "Install App"**

3. **Choose repositories**:
   - Select specific repositories or "All repositories"

### Step 3: Deploy the Server

**Local Development:**
```bash
python github_app.py
```
Server runs on `http://localhost:8000`

**Production Deployment:**
Deploy to a cloud service and update your GitHub App webhook URL.

### Step 4: Use in Pull Requests

**Option 1: Tag the bot in any PR comment:**
```
/jirald Create a task to track the changes in this PR
/jirald Make a story for this new feature
/jirald Track this as an epic for the dashboard improvements
```

**Option 2: Add the "card-required" label to any PR:**
- Simply add the `card-required` label to a PR
- The bot will automatically create a JIRA card based on the PR context
- After successful card creation, the bot will:
  - Remove the `card-required` label
  - Add a `card-created` label
- No manual comment needed

In both cases, the bot will:
- Extract PR context (title, description, files changed, author)
- Create an appropriate JIRA card with full context
- Post a comment with the JIRA issue link

## Issue Types

The system automatically chooses appropriate issue types:
- **Task** - Bug fixes, small improvements, general work
- **Story** - User features, functionality
- **Epic** - Large projects, major features
- **Subtask** - Work that's part of larger tasks

## Features

### Webhook Events
- **Issue comments** on PRs (when you tag the bot)
- **Pull request** events (for context)

### Security
- Webhook signatures are verified
- GitHub App authentication using JWT tokens
- Installation-specific access tokens

### Bot Usage
**Comment Commands:**
- `/jirald Create a task for these bug fixes`
- `/jirald Make a story for this new feature`
- `/jirald Track this refactoring work`

**Label Trigger:**
- Add `card-required` label to any PR for automatic card creation

## API Endpoints

- `GET /` - Health check
- `GET /health` - Service health status
- `POST /webhook` - GitHub webhook handler

## Troubleshooting

1. **Check server logs**: All actions are logged
2. **Verify GitHub App permissions**: Ensure correct repository permissions
3. **Test webhook delivery**: GitHub provides webhook delivery logs
4. **Environment variables**: Double-check all required vars are set
5. **Bot mention format**: Use `/jirald` not `@jirald`

## Example Workflows

**Comment-based:**
1. Create a PR with your changes
2. Add a comment: `/jirald Create a task to track these API improvements`
3. Bot analyzes PR context and creates JIRA card
4. Bot replies with JIRA issue details and link

**Label-based:**
1. Create a PR with your changes
2. Add the `card-required` label to the PR
3. Bot automatically creates a JIRA card based on PR context
4. Bot posts a comment with JIRA issue details and link
5. Bot removes `card-required` label and adds `card-created` label

## Architecture

GitHub Webhook → PR Analysis → Bedrock → JIRA → GitHub Comment

The system uses AWS Bedrock for intelligent analysis of PR context and user requests to generate appropriate JIRA cards.