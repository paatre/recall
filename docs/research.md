# An Engineering Blueprint for Automated Work-Hour Reconstruction and Logging

**Introduction: The High Cost of Context Switching and Retrospective Time Logging**

In the landscape of modern knowledge work, particularly within software development and related technical fields, a significant and often underestimated productivity drain is the "time-tracking tax." This tax is not merely the time spent interacting with logging software; it is the substantial cognitive load required to retrospectively reconstruct a work history. This process forces a developer to context-switch away from high-value tasks, painstakingly piecing together a digital trail from disparate sources like calendars, communication platforms, version control systems, and browser histories. The result is a recurring cycle of interruption that breaks mental flow, consumes hours or even days of valuable time, and introduces inaccuracies into project accounting.

The goal of this report is to provide a comprehensive technical blueprint for transforming this process from a manual, high-friction chore into an automated, intelligent system. The vision is to build a solution that passively captures and aggregates the fragmented digital exhaust of a typical workday, creating a unified and coherent work narrative. This system will serve as a "perfect memory," not only simplifying the act of logging hours but also providing a foundation for intelligent, AI-driven task categorization. Ultimately, this moves time tracking from a burdensome retrospective activity to a passive, automated background process.

This document is structured as a tiered, multi-phase implementation guide, designed to deliver incremental value at each stage. It begins by establishing a solid foundation for local activity capture on a modern Linux desktop, addressing common technical hurdles. It then progresses to the architecture of a custom data aggregator, the integration of artificial intelligence for task mapping, and finally, the end-to-end automation of time log submission. This roadmap provides a clear, actionable path for developing a bespoke solution that reclaims lost time and restores focus to the creative and technical work that truly matters.

---

Section 1: The Foundation - Automated Activity Capture on LinuxThe first and most critical step in building any automated tracking system is ensuring reliable, passive data capture at the source: the local desktop. For users of modern Linux distributions like Ubuntu, this presents a unique challenge due to the shift from the X11 display server to the more secure Wayland protocol. This section addresses this technical hurdle head-on, providing a stable foundation upon which the rest of the system can be built.1.1 The Wayland Conundrum: Security vs. IntrospectionThe difficulty in tracking application usage on contemporary Linux systems is not a bug, but a direct consequence of Wayland's architectural philosophy. Wayland is designed with security and client isolation as primary tenets, explicitly preventing applications from observing, capturing, or interfering with one another.1 This model is a stark departure from its predecessor, X11, where a global view of the window hierarchy was accessible to any application, making the development of screen-scraping and active-window-tracking tools relatively straightforward.1This security-first approach means that general-purpose activity watchers cannot function as they did on X11. Instead, they must rely on specific, opt-in Wayland protocols or desktop environment-specific APIs to gain the necessary information. The situation is further complicated by the fact that implementation of these protocols is not uniform across different Wayland compositors (the components that manage windows, like GNOME's Mutter or KDE's KWin). For instance, GNOME's Mutter has been particularly stringent, historically resisting the implementation of protocols like wlr-foreign-toplevel-management, which would simplify window tracking, due to security concerns about exposing information between applications.1 This fragmentation of the ecosystem makes a one-size-fits-all Wayland solution elusive and necessitates the use of specialized tools designed to work with a specific desktop environment.1.2 Solution A: Taming ActivityWatch on Ubuntu with WaylandActivityWatch is an excellent open-source, privacy-first tool that aligns well with the goal of local data capture.4 However, as noted, its default components struggle with Wayland. The standard aw-watcher-window is X11-only and will fail to capture window titles, reporting them as "unknown" in a Wayland session.2 Furthermore, the official aw-watcher-window-wayland is not a viable solution for GNOME or KDE Plasma users, as it depends on the wlr-foreign-toplevel-management protocol, which is not supported by their respective compositors, Mutter and KWin.3The most robust and recommended solution is to replace the default watchers with a community-developed alternative specifically designed to navigate this fragmented landscape: awatcher. This tool is a single-binary replacement for both aw-watcher-window and aw-watcher-afk and includes explicit support for GNOME on Wayland by leveraging a required GNOME Shell extension to access window information.7A step-by-step implementation guide for this setup on Ubuntu is as follows:Install the Prerequisite GNOME Extension: The awatcher tool requires the "AppId and Window Title in Wayland" GNOME extension to access the necessary metadata from Mutter. This extension must be installed and enabled before proceeding.8Install awatcher: Download the latest release of awatcher from its GitHub repository. For ease of installation, .deb packages are provided, which can be installed on Ubuntu using sudo dpkg -i aw-awatcher_*.deb.8Configure ActivityWatch: ActivityWatch's autostart behavior is controlled by a TOML configuration file. This file must be edited to prevent the default, incompatible watchers from starting and to launch awatcher instead. Locate the aw-qt.toml file (typically in ~/.config/activitywatch/aw-qt/) and modify the [autostart] section to disable the default watchers and add aw-awatcher.Restart and Verify: Restart the ActivityWatch service (aw-qt). To verify the installation, open the ActivityWatch web interface at http://localhost:5600. Navigate to the "Activity" view and confirm that the titles of your active windows are now being logged correctly, rather than appearing as "unknown." This approach has been confirmed to work effectively on recent versions like Ubuntu 24.04.7Enable Browser Tracking: For detailed tracking of web activity, which is a critical data source, the official aw-watcher-web browser extension must be installed in Firefox. This watcher captures the URL and title of the active tab, providing a much richer data stream than the window title alone.41.3 Solution B: Exploring Alternative Local-First TrackersWhile ActivityWatch provides a solid foundation, it is worth considering other open-source tools that embody different data collection and analysis philosophies. The choice between them is not merely about features but about the fundamental approach to how data is stored and processed. ActivityWatch captures activity and immediately processes it into timed "events" using a heartbeat system. In contrast, tools like arbtt store raw, periodic snapshots of system state, deferring all interpretation and categorization to the analysis stage. This distinction has profound implications for the long-term flexibility of the collected data.arbtt: The Rule-Based Powerhousearbtt (Automatic, Rule-Based Time Tracker) is a mature, command-line-driven tool that continuously captures raw data points, such as the active window title and user idle time, at regular intervals.9 Its core strength lies in its "capture now, analyze later" philosophy. All analysis is performed by applying a set of powerful, user-defined rules in a configuration file (categorize.cfg) at the moment statistics are generated.10This approach offers unparalleled flexibility. A user could collect data for years and then retroactively define a new project or category, re-analyzing their entire work history against this new rule without altering the original raw data. This is impossible with ActivityWatch's pre-processed event model. However, arbtt's strengths come with trade-offs: it lacks a graphical user interface, and its powerful rule syntax presents a steeper learning curve.9timetrackrs: The Modern Successortimetrackrs is a newer project inspired by arbtt that aims to address some of its predecessor's limitations.12 It retains the core philosophy of capturing raw, unprocessed data but enhances the user experience significantly. Data is stored in a robust SQLite database, and the tool provides a modern web UI for visualizing activity and, crucially, for creating categorization rules interactively.12timetrackrs also expands the scope of data collection, with built-in modules for tracking VS Code activity, file paths, and even connected WiFi networks to infer location.12 This provides a richer dataset for analysis out of the box. Its primary drawback is its relative immaturity; it does not yet offer pre-built binaries, requiring users to compile it from source, which presents an initial setup hurdle.12Section 2: Commercial Off-the-Shelf (COTS) Solutions: A Viability AnalysisBefore embarking on the development of a custom solution, it is prudent to evaluate whether existing commercial products can meet the core requirements. COTS solutions offer the allure of a polished user experience, cross-platform support, and zero development overhead. However, this convenience often comes at the cost of data privacy, customizability, and the very nature of the automation they provide.2.1 Market Landscape and Key Players for LinuxSeveral major players in the time-tracking market offer dedicated Linux desktop clients. The most prominent among these are Clockify, Toggl Track, and RescueTime.13 While many tools claim to offer "automatic" time tracking, it is critical to understand that this term represents a spectrum of functionality, not a binary feature.Passive & Fully Automatic Tracking: This model, exemplified by RescueTime, involves a background agent that captures all application and website usage without any user interaction. The system runs silently, requiring no starting or stopping of timers, and automatically categorizes activity to generate reports.15 This approach aligns most directly with the core problem of forgetting to log time.Timer-Based with Automatic Features: This model is employed by tools like Clockify and Toggl Track. Their desktop applications can record background activity, creating a private timeline of applications and websites used.18 However, this recorded activity does not automatically become a logged time entry. The user must manually review this timeline and explicitly convert the recorded activities into billable time entries.14 This "record-and-convert" workflow reduces the cognitive load of recalling past work but still requires a deliberate, manual step to finalize time logs.2.2 Comparative Analysis MatrixTo clarify the trade-offs between these solutions, the following table provides a detailed comparison of their key attributes.FeatureRescueTimeClockifyToggl TrackLinux ClientMature client available for Windows, macOS, and Linux.17Dedicated desktop app for Debian/Ubuntu and Redhat-based systems.13Dedicated desktop app for Linux is available.14Automation LevelFully Passive. Runs in the background, tracking all activity without manual start/stop timers.15Record-and-Convert. Auto-tracker records activity, but user must manually create time entries from the recorded data.18Record-and-Convert. Timeline feature tracks background activity, which remains private until the user converts it to time entries.14Data Privacy ModelCloud-centric. All data is sent to RescueTime's servers for processing and reporting.23Cloud-centric. Auto-tracker data is stored locally, but time entries are synced to the cloud.18Cloud-centric. Timeline data is private to the device until converted to time entries, which are then synced to the cloud.14IntegrationsIntegrates with calendars and Slack; less direct integration with developer tools like GitLab.24Extensive integrations via browser extension for GitLab, Google Calendar, and 80+ other apps.26Extensive integrations via browser extension for GitLab, Google Calendar, Slack, and 100+ other apps.29API & CustomizationAPI is available for data access, but raw event-level data for custom ML is not exposed.A public API allows for programmatic interaction with time entries and projects.13A comprehensive API allows for managing time entries, projects, and reports.32Pricing ModelPaid subscription model with a limited free tier.15Generous free tier for unlimited users and projects; paid plans add advanced features.13Generous free tier for up to 5 users; paid plans unlock advanced reporting and team features.142.3 Strategic Recommendation: The Developer's DilemmaThe choice between a COTS solution and a custom build hinges on a fundamental trade-off between convenience and control, particularly concerning data sovereignty.COTS solutions offer immediate value through polished user interfaces, mobile applications, and collaborative team features. For a user whose primary goal is to quickly implement a functional tracking system and who is comfortable with a cloud-based model, these tools present a compelling option. Among them, RescueTime is the only one that truly solves the problem of forgetting to track time, as its fully passive model requires no user interaction during the workday.However, for a power user with an interest in custom automation and AI, the case against COTS is strong.Data Sovereignty: The current workflow leverages local Firefox history, indicating a comfort level with using personal, on-device data. All COTS solutions are fundamentally cloud services, requiring that this potentially sensitive browsing and application usage data be transmitted to and stored by a third party.23 This represents a significant shift in security and privacy posture that may be unacceptable.Lack of Control and Extensibility: The ultimate goal is to build a bespoke AI pipeline to map activities to specific project tasks. COTS tools provide pre-canned analytics but do not expose the raw, granular event data necessary to train and run a custom machine learning model. The user would be confined to the vendor's ecosystem, unable to implement the custom logic they envision.Imperfect Automation: The "record-and-convert" model of Clockify and Toggl only partially solves the problem. It aids recall but still demands a manual, retrospective review and approval process, which is a significant source of the friction the user is trying to eliminate.In essence, while a COTS tool could provide a quick fix, it would foreclose the possibility of building the more powerful, private, and intelligent system the user has described. The convenience gained in the short term would come at the expense of the long-term vision.Section 3: Architecting a Custom Aggregator: A Developer's BlueprintFor a developer seeking maximum control, privacy, and extensibility, a custom-built aggregator is the superior path. This section provides a detailed architectural and implementation blueprint for creating such a system using Python, a language well-suited for this task due to its rich ecosystem of libraries for data manipulation and API interaction.3.1 System Architecture: A Modular, Python-Based PipelineThe proposed architecture is a modular pipeline designed for simplicity, reliability, and ease of extension. It consists of four primary components:Data Collectors: A series of independent Python scripts, each responsible for fetching data from a single source (e.g., collect_firefox.py, collect_gitlab.py). This modularity ensures that a failure in one collector does not impact the others and makes it simple to add new data sources in the future.Scheduler: On Ubuntu, systemd timers are a modern and robust alternative to cron for scheduling the execution of the collector scripts at regular intervals (e.g., once per hour). They offer more granular control and better logging capabilities.Data Store: A central SQLite database is the ideal choice for this application. It is a serverless, file-based database engine that is natively supported by Python's sqlite3 module. It requires no complex setup, is highly portable, and is more than capable of handling the volume of data generated by a single user.Unified Schema: To normalize the disparate data sources, all collected information will be stored in a single table, events, with a universal schema. This simplifies querying and analysis. A proposed schema is:id: INTEGER PRIMARY KEY AUTOINCREMENTtimestamp: TEXT (ISO 8601 format in UTC)source: TEXT (e.g., 'firefox', 'gitlab', 'gcal', 'slack')event_type: TEXT (e.g., 'visit', 'commit', 'comment', 'meeting', 'message')summary: TEXT (The primary text content, e.g., page title, commit message)url: TEXT (A direct link to the resource, if available)raw_data: TEXT (A JSON blob of the original data for future reference)3.2 Implementation Guide: Data Collector ScriptsWhat follows are practical, code-centric guides for implementing each of the required data collectors.Firefox History CollectorAccessing live browser data presents a unique challenge: the database file is locked while the browser is running.34 A robust collector must therefore not attempt to read the live file directly. The correct and reliable approach is the "copy-on-read" pattern: the script's first action is to create a temporary copy of the history database and then perform its queries on that copy.Firefox stores browsing history in a file named places.sqlite located within the user's profile directory (e.g., ~/.mozilla/firefox/<profile_id>/).34Pythonimport sqlite3
import shutil
import os
import glob

def collect_firefox_history():
    # Find the Firefox profile directory
    profile_path = glob.glob(os.path.expanduser('~/.mozilla/firefox/*.default-release'))
    history_db = os.path.join(profile_path, 'places.sqlite')
    
    # Copy the database to a temporary location to avoid lock errors
    temp_db = '/tmp/firefox_history.sqlite'
    shutil.copyfile(history_db, temp_db)
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Query to join history visits with place URLs and titles
    query = """
    SELECT
        h.visit_date,
        p.url,
        p.title
    FROM moz_historyvisits AS h
    LEFT JOIN moz_places AS p ON h.place_id = p.id
    WHERE h.visit_date > (strftime('%s', 'now') - 86400) * 1000000; -- Last 24 hours
    """
    
    events =
    for row in cursor.execute(query):
        # visit_date is in microseconds since epoch, convert to ISO 8601
        timestamp_iso = datetime.fromtimestamp(row / 1000000).isoformat()
        event = {
            'timestamp': timestamp_iso,
            'source': 'firefox',
            'event_type': 'visit',
            'summary': row,
            'url': row
        }
        events.append(event)
        
    conn.close()
    os.remove(temp_db)
    
    # Here, you would insert the 'events' list into your central SQLite DB
    return events
Google Calendar API CollectorInteracting with Google APIs requires setting up a project in the Google Cloud Console and handling OAuth 2.0 authentication. This is a one-time setup cost that enables secure, programmatic access to calendar data.Setup: In the Google Cloud Console, create a new project, enable the "Google Calendar API," and create "OAuth 2.0 Client IDs" credentials for a "Desktop app." Download the resulting credentials.json file.37Authentication: The google-auth-oauthlib library simplifies the OAuth flow. The first time the script runs, it will open a browser window for user consent. Subsequent runs will use the token.json file it creates to refresh the access token non-interactively.38Pythonfrom google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os.path
import datetime

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def collect_gcal_events():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    
    # Get events from the last 24 hours
    now = datetime.datetime.utcnow()
    time_min = (now - datetime.timedelta(days=1)).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary', timeMin=time_min,
        maxResults=100, singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    gcal_events = events_result.get('items',)
    events =
    for event in gcal_events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        event_data = {
            'timestamp': start,
            'source': 'gcal',
            'event_type': 'meeting',
            'summary': event['summary'],
            'url': event.get('htmlLink')
        }
        events.append(event_data)
        
    # Insert into central DB
    return events
GitLab API CollectorThe GitLab API is straightforward to use with a Personal Access Token (PAT).Authentication: In GitLab user settings, navigate to "Access Tokens." Create a new token with the read_api scope. Securely store this token.40Library: The python-gitlab library provides a clean, object-oriented interface to the GitLab API.41Pythonimport gitlab
import os
import datetime

def collect_gitlab_activity():
    gl = gitlab.Gitlab('https://gitlab.com', private_token=os.environ.get('GITLAB_PAT'))
    gl.auth() # Authenticate and get current user
    
    # Get events from the last 24 hours
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()
    
    # The events API provides a user-centric activity stream
    user_events = gl.events.list(all=True, after=since)
    
    events =
    for event in user_events:
        summary = ''
        if event.action_name == 'pushed to':
            # For push events, you might want to get commit messages
            project = gl.projects.get(event.project_id)
            commit = project.commits.get(event.push_data['commit_to'])
            summary = commit.title
        elif event.action_name == 'commented on':
            summary = event.note['body']
        else:
            summary = f"{event.action_name} {event.target_type or ''}"

        event_data = {
            'timestamp': event.created_at,
            'source': 'gitlab',
            'event_type': event.action_name,
            'summary': summary,
            'url': event.target_url if hasattr(event, 'target_url') else None
        }
        events.append(event_data)
        
    # Insert into central DB
    return events
Slack API CollectorAccessing Slack data requires creating a Slack App within the workspace to obtain a bot token.Setup: Go to api.slack.com/apps, create a new app, and add the necessary Bot Token Scopes under "OAuth & Permissions." Required scopes will include channels:history, groups:history (for private channels), im:history (for DMs), and users:read (to map user IDs to names).43 Install the app to the workspace to generate the Bot User OAuth Token.Library: The official slack-sdk for Python is the recommended tool.44Pythonimport slack_sdk
import os
import datetime

def collect_slack_messages():
    client = slack_sdk.WebClient(token=os.environ)
    user_id = client.auth_test()['user_id']
    
    # Get messages from the last 24 hours
    oldest = (datetime.datetime.now() - datetime.timedelta(days=1)).timestamp()
    
    all_messages =
    for conv in client.conversations_list(types="public_channel,private_channel,im"):
        for channel in conv['channels']:
            try:
                history = client.conversations_history(
                    channel=channel['id'],
                    oldest=oldest
                )
                for message in history['messages']:
                    if message.get('user') == user_id:
                        timestamp_iso = datetime.datetime.fromtimestamp(float(message['ts'])).isoformat()
                        message_data = {
                            'timestamp': timestamp_iso,
                            'source': 'slack',
                            'event_type': 'message',
                            'summary': message['text'],
                            'url': f"https://{client.team_info()['team']['domain']}.slack.com/archives/{channel['id']}/p{message['ts'].replace('.', '')}"
                        }
                        all_messages.append(message_data)
            except Exception as e:
                # Handle cases like not being in a channel
                pass
                
    # Insert into central DB
    return all_messages
Section 4: From Raw Data to Actionable Insights: The AI-Powered Task MapperWith a unified stream of activity data flowing into a central database, the next phase is to interpret this data, mapping raw event summaries to specific projects and tasks. This is where artificial intelligence, specifically Natural Language Processing (NLP), can provide a powerful solution, transforming a manual categorization chore into an automated process. The challenge can be framed as a multi-class text classification problem: given an input text (a commit message, URL title, etc.), assign it to one of N predefined project labels.46The primary obstacle in any supervised machine learning task is the need for a large, manually labeled training dataset.48 Creating such a dataset is a significant project in itself. Fortunately, recent advancements in large language models (LLMs) offer a "zero-shot" learning approach that dramatically lowers this barrier to entry, providing a powerful starting point with minimal effort.4.1 Path A: The Zero-Shot Learning Approach (Low Effort, High Impact)Zero-Shot Classification (ZSC) is a paradigm in which a model can classify text into categories it has not been explicitly trained on.51 This is achieved by leveraging models pre-trained on a related task called Natural Language Inference (NLI). In NLI, a model determines the relationship between a "premise" (the input text) and a "hypothesis" (a statement). For ZSC, the candidate labels are dynamically converted into hypotheses. For example, if the input text is Refactor authentication service and the candidate labels are Project Phoenix and Internal Tools, the model internally evaluates hypotheses like "This text is about Project Phoenix" and "This text is about Internal Tools," assigning a probability score to each.52This approach is a perfect fit for this use case because it requires zero labeled training data. The user's existing list of project and task names can be used directly as the candidate labels at inference time. This makes the system incredibly agile; when a new project starts, its name is simply added to the list of candidate labels, with no model retraining required.The Hugging Face transformers library provides a high-level pipeline API that makes implementing ZSC remarkably simple.51Pythonfrom transformers import pipeline

# This will download the model on first run. 
# facebook/bart-large-mnli is a popular choice for this task.
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

def classify_activity(activity_summary, project_labels):
    """
    Classifies an activity summary using a zero-shot model.
    
    Args:
        activity_summary (str): The text description of the activity.
        project_labels (list): A list of project/task names to classify against.
        
    Returns:
        dict: A dictionary of labels and their corresponding scores.
    """
    # multi_label=False assumes only one project can be correct, which is typical for time logging.
    # The scores will sum to 1.0.
    result = classifier(activity_summary, project_labels, multi_label=False)
    
    # The output is sorted from highest score to lowest
    return dict(zip(result['labels'], result['scores']))

# Example Usage:
commit_message = "feat: add user profile page to new customer portal"
projects =

classification = classify_activity(commit_message, projects)
print(classification)
# Expected Output might be:
# {'Project Phoenix': 0.85, 'Internal Tools': 0.10, 'Bug Fixes': 0.04, 'Project Chimera': 0.01}
4.2 Path B: The Traditional ML Approach (High Effort, Maximum Accuracy)If the accuracy of the zero-shot approach proves insufficient for specific needs, a custom classifier can be trained. This path offers the potential for higher accuracy because the model is fine-tuned on the user's own data and vocabulary. However, it requires a significant upfront investment in data labeling.Create a Labeled Dataset: This is the most critical and time-consuming step. The user must manually review a subset of their aggregated activity data (from the SQLite database) and assign the correct project/task label to each entry. A starting point of 50-100 examples per category is recommended to build a reasonable baseline model.50Feature Extraction (TF-IDF): Text must be converted into a numerical format that machine learning models can understand. A standard and highly effective method is Term Frequency-Inverse Document Frequency (TF-IDF). This technique creates a vector for each document where each dimension corresponds to a word in the vocabulary, and the value is a weight that reflects how important that word is to the document in the context of the entire corpus.53Train a Classifier: For text classification tasks, simple linear models often perform exceptionally well and are computationally efficient. A Linear Support Vector Classifier (LinearSVC) is an excellent choice, as is Logistic Regression.47 The scikit-learn library provides robust implementations of these algorithms and the entire training pipeline.Pythonfrom sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score

# Assume 'df' is a pandas DataFrame loaded from the SQLite DB
# with 'summary' and 'project_label' columns, created in Step 1.

# 1. Split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(
    df['summary'], df['project_label'], test_size=0.2, random_state=42
)

# 2. Initialize and fit the TF-IDF Vectorizer
vectorizer = TfidfVectorizer(min_df=2, ngram_range=(1, 2), stop_words='english', sublinear_tf=True)
X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)

# 3. Train the LinearSVC model
model = LinearSVC()
model.fit(X_train_tfidf, y_train)

# 4. Evaluate the model
y_pred = model.predict(X_test_tfidf)
print(f"Model Accuracy: {accuracy_score(y_test, y_pred):.2f}")
An alternative integrated toolkit for this approach is spaCy, which offers a TextCategorizer component to build and train text classification models within its unified NLP pipeline.574.3 Comparative Analysis of AI ApproachesThe decision between these two paths depends entirely on the trade-off between initial effort and desired accuracy.FeatureZero-Shot Classification (Hugging Face)Custom Classifier (Scikit-learn)Data Labeling EffortNone. Uses the list of project names as dynamic labels at runtime.52Significant. Requires manual labeling of hundreds of data points to create a training set.48Implementation ComplexityLow. Requires only a few lines of code using the transformers pipeline.51Medium. Involves data splitting, vectorization, model training, and evaluation steps.53Computational CostHigh at inference time (uses a large transformer model).Low at inference time after a more intensive, one-off training phase.AdaptabilityExcellent. New projects can be added to the label list without retraining.Poor. The model is static; adding a new project requires new labeled data and full retraining.Potential AccuracyGood. Provides a strong baseline but may struggle with highly nuanced or domain-specific vocabulary.Potentially Excellent. Can achieve very high accuracy as it is fine-tuned to the user's specific data and language patterns.For this specific use case, the Zero-Shot approach offers a near-perfect balance of performance and practicality. It eliminates the single greatest barrier—data labeling—while providing a system that is inherently adaptable to the dynamic nature of project work. It is the recommended starting point.Section 5: Closing the Loop - Strategies for Time Log SubmissionThe final stage of this project is to leverage the aggregated and classified data to fulfill the primary objective: logging work hours with minimal friction. The system developed thus far provides immediate value even before full automation is implemented, and it serves as the perfect data source for programmatic submission.5.1 Immediate Value: The "Perfect Memory" DashboardEven without the final submission step, the centralized SQLite database of activities is an immensely powerful tool. It fundamentally changes the nature of manual time logging. The task is transformed from a difficult problem of recall ("What did I work on last Tuesday at 2 PM?") to a simple problem of recognition ("Here is what I was doing; how should it be categorized?").A simple script or a basic web interface (e.g., using Flask or Streamlit) can query the database and present a chronological, unified list of all activities for a given day. This "perfect memory" dashboard drastically reduces the cognitive load and time required for manual entry.When combined with the AI task mapper from Section 4, this dashboard becomes even more powerful. The interface can display each activity alongside the AI's predicted project label. The user's role then shifts from data entry to simple verification, reviewing the AI's suggestions and making corrections where necessary before submitting the hours in their company's tool. This "human-in-the-loop" system represents a massive improvement over the current manual process.5.2 The Final Step: Programmatic Submission via GraphQLThe ultimate goal of end-to-end automation is achievable because the target time-tracking software exposes a GraphQL API. GraphQL is a modern, strongly-typed API query language that is ideal for this kind of programmatic interaction.The gql library is a robust and widely used Python client for interacting with GraphQL APIs, supporting both synchronous and asynchronous operations.60 The process for implementing the submission script involves three key steps:Authentication: The GraphQL API will almost certainly require an authentication token (e.g., a personal access token or an OAuth token) to be passed in the HTTP headers of each request. This token must be obtained from the time-tracking software's user settings or developer portal.Discovering the Mutation: GraphQL uses queries to fetch data and mutations to change data. The user will need to find the specific mutation for logging work. This can typically be found in the API documentation or by using a GraphQL IDE (like GraphiQL or Apollo Studio), which is often provided by the service. The mutation will define the required arguments, such as taskId, durationInMinutes, date, and notes.Executing the Mutation: The Python script will use the gql library to construct and execute this mutation, passing in the data derived from the aggregated and classified activity logs.Pythonfrom gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
import os

# 1. Set up the transport with authentication headers
url = "https://api.yourcompany.com/graphql"
token = os.environ.get("TIME_TRACKER_TOKEN")
headers = {"Authorization": f"Bearer {token}"}

transport = AIOHTTPTransport(url=url, headers=headers)

# 2. Create the GQL client
client = Client(transport=transport, fetch_schema_from_transport=True)

# 3. Define the GraphQL mutation (this is an example, the actual mutation will vary)
log_work_mutation = gql("""
    mutation LogWork($taskId: ID!, $duration: Int!, $date: ISO8601Date!, $notes: String) {
        logWorkEntry(input: {
            taskId: $taskId,
            durationMinutes: $duration,
            entryDate: $date,
            notes: $notes
        }) {
            id
            durationMinutes
        }
    }
""")

# Example data to submit
# This data would be generated by processing the events from the SQLite DB
params = {
    "taskId": "task-id-from-your-system",
    "duration": 60, # in minutes
    "date": "2024-08-15",
    "notes": "Refactored user service caching based on GitLab commit xyz."
}

# 4. Execute the mutation
try:
    result = client.execute(log_work_mutation, variable_values=params)
    print("Successfully logged work:", result)
except Exception as e:
    print("An error occurred:", e)
By combining the aggregated data, the AI-powered classification, and this GraphQL submission script, the entire process of logging work hours can be reduced to running a single command.Conclusion & Tiered Implementation StrategyThe challenge of retrospective time logging is a significant yet solvable drain on productivity. By systematically leveraging modern tools for local data capture, API integration, and artificial intelligence, it is possible to construct a powerful, personalized automation system. This system not only eliminates a tedious administrative chore but also serves as a compelling example of applying development skills to improve one's own workflow.The analysis has shown that while commercial tools offer convenience, a custom-built solution provides superior privacy, control, and extensibility, aligning better with a developer's needs and capabilities. The key technical hurdles—such as activity tracking on Wayland and navigating various API authentication schemes—are well-understood problems with robust solutions. Furthermore, the advent of zero-shot learning models dramatically lowers the barrier to entry for intelligent task classification, making an AI-enhanced system feasible without the prohibitive cost of manual data labeling.To translate these findings into an actionable plan, the following phased implementation strategy is recommended. This approach allows for the delivery of incremental value at each stage, ensuring that the project provides benefits long before its final completion.Phase 1: The Quick Win (Establish a Source of Truth)Action: Install and configure ActivityWatch on the Ubuntu desktop, replacing the default watchers with awatcher to ensure compatibility with the Wayland display server. Install the Firefox web watcher extension.Immediate Benefit: A reliable, private, and local source of truth for application, window, and browsing activity is established. This alone provides a valuable reference for manual time logging.Phase 2: The Unified View (Aggregate All Context)Action: Develop the modular Python-based aggregator. Implement the individual collector scripts for Firefox, Google Calendar, GitLab, and Slack, and create the central SQLite database to store all activity in a unified schema.Immediate Benefit: This solves the "where do I look?" problem. A single, searchable database now contains a complete chronological record of work context, transforming the manual logging process from one of recall to one of recognition.Phase 3: Intelligent Automation (Add AI-Powered Suggestions)Action: Integrate the Hugging Face transformers library and implement the zero-shot classification pipeline. Connect this pipeline to the aggregated data to automatically generate project/task suggestions for each activity.Immediate Benefit: The cognitive load of categorization is drastically reduced. What previously took hours of manual classification can now be accomplished in minutes of verification and approval.Phase 4: End-to-End Automation (Close the Loop)Action: Implement the final Python script to interact with the company's time-tracking software via its GraphQL API. This script will read the verified, AI-classified data and programmatically submit the time logs.Immediate Benefit: The "holy grail" of one-click or fully automated time logging is achieved, effectively eliminating the time-tracking tax and freeing up valuable time and mental energy for more critical work.
