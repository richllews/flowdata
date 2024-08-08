from imports import *
from constants import *

import argparse
import requests
from requests.auth import HTTPBasicAuth
import json
import csv
from datetime import datetime

# Additional import
from datetime import timedelta



# Set up argument parsing
parser = argparse.ArgumentParser(description='Fetch JIRA tickets for a specific sprint.')
parser.add_argument('--sprint', required=True, help='The ID of the sprint')
#parser.add_argument('--sprint_ids', nargs='+', required=True, help='The IDs of the sprints, separated by space')
args = parser.parse_args()



# Basic Authentication
auth = HTTPBasicAuth(email, api_token)

# Headers
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# Function to parse datetime
def parse_datetime(date_str):
    return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%d %H:%M:%S')

# Function to fetch issue changelog
def fetch_issue_changelog(issue_key):
    changelog_url = f"https://theplatform.jira.com/rest/api/3/issue/{issue_key}/changelog"
    response = requests.get(changelog_url, headers=headers, auth=auth)

    if response.status_code == 200:
        return json.loads(response.text)['values']
    else:
        raise Exception(f"Failed to retrieve changelog for {issue_key}: {response.text}")

# Function to collect status transition dates
def get_status_transition_dates(issue_key):
    changelog = fetch_issue_changelog(issue_key)
    status_dates = {}

    for change in changelog:
        for item in change['items']:
            if item['field'] == 'status':
                status = item['toString']
                date = parse_datetime(change['created'])
                if status not in status_dates:  # Record the first transition to each status
                    status_dates[status] = date
    return status_dates

# Function to fetch issues with pagination
def fetch_issues(start_at=0):
    issues = []
    while True:
        query = {
            'jql': f'Sprint = {sprint} AND status IN ("Testing", "Approved for Release", "Closed")',
            'maxResults': 100,
            'fields': f'summary,key,issuetype,status,created,{story_points_field},priority',
            'startAt': start_at
        }

        response = requests.get(url, headers=headers, params=query, auth=auth)
        if response.status_code == 200:
            data = json.loads(response.text)
            issues.extend(data['issues'])
            if data['startAt'] + data['maxResults'] >= data['total']:
                break
            else:
                start_at += data['maxResults']
        else:
            raise Exception(f"Failed to retrieve issues: {response.text}")

    return issues

# Function to parse datetime without formatting
def parse_datetime_raw(date_str):
    return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f%z')

# Modified function to include blocked days calculation
def get_blocked_days(issue_key):
    changelog = fetch_issue_changelog(issue_key)
    blocked_dates = []
    blocked_days = 0

    for change in changelog:
        for item in change['items']:
            if item['field'] == 'status' and (item['toString'] == 'Blocked' or item['fromString'] == 'Blocked'):
                date = parse_datetime_raw(change['created'])
                # Record every transition in and out of "Blocked"
                blocked_dates.append(date)

    # Calculate total blocked time
    for i in range(0, len(blocked_dates), 2):
        start_date = blocked_dates[i]
        end_date = blocked_dates[i + 1] if i + 1 < len(blocked_dates) else datetime.now(datetime.timezone.utc)
        blocked_days += (end_date - start_date).days

    return blocked_days

# Fetch all issues
issues = fetch_issues()

# Define the order of status fields
status_order = ['In Progress', 'Peer Review','Pending Deployment','Testing', 'Approved for Release', 'Closed']

# Write to CSV
with open('flow-metrics.csv', mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['Key', 'Created Date'] + status_order + ['Issue Type', 'Story Points', 'Priority','Blocked Days'])

    for issue in issues:
        key = issue['key']
        summary = issue['fields']['summary']
        issue_type = issue['fields']['issuetype']['name']
        story_points = issue['fields'].get(story_points_field, '')
        created_date = parse_datetime(issue['fields']['created'])
        current_status = issue['fields']['status']['name']
        priority = issue['fields']['priority']['name']
        status_dates = get_status_transition_dates(key)
        blocked_days = get_blocked_days(key)
        writer.writerow([key, created_date] + [status_dates.get(status, '') for status in status_order] + [issue_type, story_points, priority, blocked_days])

print("Data written to flow-metrics.csv")
