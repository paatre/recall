sources:
  - id: "Firefox"
    type: "firefox"
    enabled: true
    config: {}

  - id: "Calendar"
    type: "gcalendar"
    enabled: true
    config: {}

  - id: "GitLab"
    type: "gitlab"
    enabled: true
    config:
      url: ""
      private_token: ""
      user_id: 0

  - id: "Shell"
    type: "shell"
    enabled: true
    config: {}

  - id: "Slack"
    type: "slack"
    enabled: true
    config:
      user_token: ""

llm:
  provider: "github" # "github", "openai", or "custom"
  model: ""          # Optional. Model to use (e.g. gpt-4o, llama3).
  api_key: ""        # Optional. If empty, uses 'gh' CLI for github, or OPENAI_API_KEY
  base_url: ""       # Optional. Set to override default API endpoint
  events_per_chunk: 150              # Number of events sent per API call
  max_event_description_length: 200  # Truncates long event descriptions to save context
  custom_instructions: ""
