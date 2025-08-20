#!/usr/bin/env python3
"""
Test script for GitHub App configuration
"""

import os
import json
from dotenv import load_dotenv
from github_app import GitHubJiraBot

load_dotenv()

def test_configuration():
    """Test GitHub App configuration"""
    print("🔍 Testing GitHub App Configuration...")
    print("=" * 50)
    
    # Check required environment variables
    required_vars = {
        'GITHUB_APP_ID': os.getenv('GITHUB_APP_ID'),
        'GITHUB_PRIVATE_KEY': os.getenv('GITHUB_PRIVATE_KEY'),
        'GITHUB_WEBHOOK_SECRET': os.getenv('GITHUB_WEBHOOK_SECRET'),
        'JIRA_URL': os.getenv('JIRA_URL'),
        'JIRA_USERNAME': os.getenv('JIRA_USERNAME'),
        'JIRA_API_TOKEN': os.getenv('JIRA_API_TOKEN'),
        'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID'),
    }
    
    missing = []
    for var, value in required_vars.items():
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 20)}")
        else:
            print(f"❌ {var}: Not set")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️  Missing variables: {', '.join(missing)}")
        
        # If only GitHub vars are missing, test JIRA separately
        github_vars = ['GITHUB_APP_ID', 'GITHUB_PRIVATE_KEY', 'GITHUB_WEBHOOK_SECRET']
        github_missing = [var for var in missing if var in github_vars]
        jira_aws_missing = [var for var in missing if var not in github_vars]
        
        if github_missing and not jira_aws_missing:
            print("\n🔍 Testing JIRA integration separately...")
            try:
                from mvp_jira_client import SimpleJiraClient
                jira_client = SimpleJiraClient()
                jira_result = jira_client.create_issue(
                    summary="Test issue from GitHub App configuration test",
                    description="This is a test issue to verify JIRA integration works",
                    issue_type="Task"
                )
                
                if jira_result.get('success'):
                    print(f"✅ JIRA integration works: {jira_result['issue_key']}")
                    print("\n📋 To complete setup:")
                    print("1. Create GitHub App (see github_app_setup.md)")
                    print("2. Add GitHub environment variables to .env")
                    print("3. Re-run this test")
                    return True
                else:
                    print(f"❌ JIRA integration failed: {jira_result.get('error')}")
                    return False
            except Exception as e:
                print(f"❌ JIRA test failed: {e}")
                return False
        
        return False
    
    # Test GitHub App initialization
    try:
        bot = GitHubJiraBot()
        print("\n✅ GitHub App bot initialized successfully")
        
        # Test JWT token generation
        jwt_token = bot._get_jwt_token()
        print("✅ JWT token generation works")
        
        # Test JIRA client
        jira_result = bot.jira_client.create_issue(
            summary="Test issue from GitHub App",
            description="This is a test issue to verify the integration works",
            issue_type="Task"
        )
        
        if jira_result.get('success'):
            print(f"✅ JIRA integration works: {jira_result['issue_key']}")
        else:
            print(f"❌ JIRA integration failed: {jira_result.get('error')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ GitHub App initialization failed: {e}")
        return False

def test_pr_context_extraction():
    """Test PR context extraction"""
    print("\n🔍 Testing PR Context Extraction...")
    print("=" * 50)
    
    # Mock PR data
    mock_pr_data = {
        'title': 'Fix login timeout bug',
        'body': 'This PR fixes the timeout issue when users stay logged in too long.',
        'user': {'login': 'testuser'},
        'head': {'ref': 'fix-login-timeout'},
        'base': {'ref': 'main', 'repo': {'full_name': 'company/repo'}},
        'html_url': 'https://github.com/company/repo/pull/123',
        'number': 123,
        'additions': 15,
        'deletions': 3,
        'commits': 2,
        'changed_files': [
            {'filename': 'src/auth/login.py'},
            {'filename': 'tests/test_auth.py'}
        ]
    }
    
    try:
        bot = GitHubJiraBot()
        context = bot.extract_pr_context(mock_pr_data)
        
        print("✅ PR context extracted:")
        print(f"  Title: {context['title']}")
        print(f"  Author: {context['author']}")
        print(f"  Repository: {context['repository']}")
        print(f"  Files changed: {len(context['files_changed'])}")
        print(f"  Changes: +{context['additions']} -{context['deletions']}")
        
        return True
        
    except Exception as e:
        print(f"❌ PR context extraction failed: {e}")
        return False

async def test_end_to_end():
    """Test end-to-end JIRA card creation"""
    print("\n🔍 Testing End-to-End Card Creation...")
    print("=" * 50)
    
    mock_pr_context = {
        'title': 'Add user profile feature',
        'description': 'This PR adds the ability for users to customize their profiles',
        'author': 'developer123',
        'branch': 'feature-user-profiles',
        'base_branch': 'main',
        'url': 'https://github.com/company/repo/pull/124',
        'number': 124,
        'repository': 'company/mobile-app',
        'files_changed': ['src/components/Profile.tsx', 'src/api/user.ts'],
        'additions': 85,
        'deletions': 12,
        'commits': 4
    }
    
    user_request = "Create a story for this new user profile feature"
    
    try:
        bot = GitHubJiraBot()
        result = await bot.create_jira_card_from_pr(mock_pr_context, user_request)
        
        if result.get('success'):
            print(f"✅ JIRA card created successfully:")
            print(f"  Issue: {result['issue_key']}")
            print(f"  URL: {result['url']}")
        else:
            print(f"❌ Card creation failed: {result.get('error')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 GitHub App Configuration Test")
    print("=" * 60)
    
    tests = [
        ("Configuration", test_configuration),
        ("PR Context Extraction", test_pr_context_extraction),
        ("End-to-End Integration", test_end_to_end)
    ]
    
    passed = 0
    for name, test_func in tests:
        print(f"\n📋 {name}:")
        try:
            if hasattr(test_func, '__call__'):
                if test_func.__name__.startswith('test_end'):
                    result = await test_func()
                else:
                    result = test_func()
                if result:
                    passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")
    
    if passed == len(tests):
        print("\n🎉 All tests passed! GitHub App is ready!")
        print("\n📋 Next steps:")
        print("1. Create your GitHub App (see github_app_setup.md)")
        print("2. Deploy the server: python github_app.py")
        print("3. Install the app on your repositories")
        print("4. Test by tagging @jira-bot in a PR comment")
    else:
        print(f"\n❌ {len(tests) - passed} test(s) failed.")
        print("Please check your configuration and try again.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())