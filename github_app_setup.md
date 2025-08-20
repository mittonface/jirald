# GitHub App Setup Guide

This guide helps you create and configure a GitHub App that creates JIRA cards from PR context.

## Step 1: Create GitHub App

1. **Go to GitHub Settings**:
   - Personal account: `https://github.com/settings/apps`
   - Organization: `https://github.com/organizations/YOUR_ORG/settings/apps`

2. **Click "New GitHub App"**

3. **Configure Basic Information**:
   - **App name**: `JIRA Card Creator` (or your preferred name)
   - **Description**: `Creates JIRA cards from PR context when tagged`
   - **Homepage URL**: `https://your-domain.com` (or your website)
   - **Webhook URL**: `https://your-server.com/webhook` (where you'll host this)
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

5. **Where can this GitHub App be installed?**:
   - Select "Only on this account" or "Any account" based on your needs

6. **Create the app** and note down:
   - **App ID** (you'll need this)
   - **Download the private key** (.pem file)

## Step 2: Configure Environment Variables

Add these to your `.env` file:

```bash
# GitHub App Configuration
GITHUB_APP_ID=your_app_id_here
GITHUB_PRIVATE_KEY=/path/to/your/private-key.pem
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here

# Existing JIRA and AWS config stays the same
JIRA_URL=https://yourcompany.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token

AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret
```

## Step 3: Install the App on Repository

1. **Go to your GitHub App page**:
   - `https://github.com/settings/apps/YOUR_APP_NAME`

2. **Click "Install App"**

3. **Choose repositories**:
   - Select specific repositories where you want the bot
   - Or select "All repositories" for organization-wide access

## Step 4: Deploy the Server

### Option A: Local Development
```bash
# Install dependencies
uv sync

# Run the server
python github_app.py
```

The server will run on `http://localhost:8000`

### Option B: Production Deployment

Deploy to a cloud service (Heroku, AWS, etc.) and update your GitHub App webhook URL to point to your server.

## Step 5: Test the Integration

1. **Create a Pull Request** in a repository where the app is installed

2. **Tag the bot in a comment**:
   ```
   @jira-bot Create a task to track the changes in this PR
   ```

3. **The bot will**:
   - Analyze the PR context (files changed, description, etc.)
   - Use AI to create an appropriate JIRA card
   - Post a comment with the JIRA issue link

## Usage Examples

**In any PR comment, mention the bot:**

- `@jira-bot Create a task for these bug fixes`
- `@jira-bot Make a story for this new feature`
- `@jira-bot Track this as an epic for the dashboard improvements`

The bot will automatically:
- Extract PR context (title, description, files changed, author)
- Combine with your request
- Create an appropriate JIRA card with full context
- Link back to the PR

## Webhook Events

The app listens for:
- **Issue comments** on PRs (when you tag the bot)
- **Pull request** events (for context)

## Security

- Webhook signatures are verified
- GitHub App authentication using JWT tokens
- Installation-specific access tokens

## Troubleshooting

1. **Check logs**: The server logs all actions
2. **Verify permissions**: Ensure the app has correct repository permissions
3. **Test webhook**: GitHub provides webhook delivery logs
4. **Environment variables**: Double-check all required vars are set