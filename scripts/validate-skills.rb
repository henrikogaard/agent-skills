#!/usr/bin/env ruby
# Validate the repository catalog without external dependencies.

require_relative "../lib/agent_skills/catalog"

root = File.expand_path("..", __dir__)
catalog = AgentSkills::Catalog.new(root)
errors = catalog.validate

if errors.empty?
  puts "Validated #{catalog.skills.length} custom skills; manifest and README links OK."
else
  warn errors.join("\n")
  exit 1
end
