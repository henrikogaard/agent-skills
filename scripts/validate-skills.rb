#!/usr/bin/env ruby
# Validate the portable skill repo without external dependencies.

require "yaml"

root = File.expand_path("..", __dir__)
ignored_dirs = %w[agent-skills]

skills = Dir.children(root).select do |entry|
  path = File.join(root, entry)
  File.directory?(path) &&
    File.exist?(File.join(path, "SKILL.md")) &&
    !ignored_dirs.include?(entry)
end.sort

readme_path = File.join(root, "README.md")
readme = File.exist?(readme_path) ? File.read(readme_path) : ""

errors = []

skills.each do |skill|
  skill_path = File.join(root, skill, "SKILL.md")
  text = File.read(skill_path)
  frontmatter = text[/\A---\n(.*?)\n---/m, 1]

  if frontmatter.nil?
    errors << "#{skill}: missing YAML frontmatter"
    next
  end

  begin
    data = YAML.safe_load(frontmatter, permitted_classes: [], aliases: false)
  rescue Psych::SyntaxError => e
    errors << "#{skill}: invalid YAML frontmatter: #{e.message}"
    next
  end

  errors << "#{skill}: frontmatter name does not match folder" unless data["name"] == skill
  errors << "#{skill}: missing description" if data["description"].to_s.strip.empty?
  errors << "#{skill}: description is over 500 characters" if data["description"].to_s.length > 500
  errors << "#{skill}: missing README catalog link" unless readme.include?("[`#{skill}`](#{skill}/SKILL.md)")

  openai_path = File.join(root, skill, "agents", "openai.yaml")
  unless File.exist?(openai_path)
    errors << "#{skill}: missing agents/openai.yaml"
    next
  end

  begin
    openai = YAML.safe_load(File.read(openai_path), permitted_classes: [], aliases: false)
  rescue Psych::SyntaxError => e
    errors << "#{skill}: invalid agents/openai.yaml: #{e.message}"
    next
  end

  errors << "#{skill}: missing interface.display_name" if openai.dig("interface", "display_name").to_s.strip.empty?
  errors << "#{skill}: missing interface.short_description" if openai.dig("interface", "short_description").to_s.strip.empty?
  errors << "#{skill}: missing interface.default_prompt" if openai.dig("interface", "default_prompt").to_s.strip.empty?
  errors << "#{skill}: policy.allow_implicit_invocation should be true" unless openai.dig("policy", "allow_implicit_invocation") == true
end

links = readme.scan(/\]\(([^)]+)\)/).flatten.reject { |link| link.start_with?("http") }
links.each do |link|
  errors << "README: missing relative link target #{link}" unless File.exist?(File.join(root, link))
end

if errors.empty?
  puts "Validated #{skills.length} custom skills; README links OK."
else
  warn errors.join("\n")
  exit 1
end
