# frozen_string_literal: true

require "yaml"

module AgentSkills
  class Catalog
    ALLOWED_CLASSES = %w[portable codex].freeze
    ALLOWED_TARGETS = %w[agents codex].freeze
    NAME_PATTERN = /\A[a-z0-9]+(?:-[a-z0-9]+)*\z/
    REQUIRED_FIELDS = %w[path class targets ownership publication update_policy].freeze

    attr_reader :root, :manifest, :errors

    def initialize(root)
      @root = File.expand_path(root)
      @errors = []
      loaded_manifest = load_yaml(File.join(@root, "config", "skills.yaml"), "manifest")
      if loaded_manifest && !loaded_manifest.is_a?(Hash)
        @errors << "manifest: root must be a mapping"
      end
      @manifest = loaded_manifest.is_a?(Hash) ? loaded_manifest : {}
      @manifest_load_errors = @errors.dup
    end

    def skills
      value = manifest["skills"]
      value.is_a?(Hash) ? value : {}
    end

    def validate
      errors.replace(@manifest_load_errors)
      validate_manifest_shape
      validate_entries
      validate_public_repository_boundary
      validate_public_content
      validate_filesystem_coverage
      validate_target_collisions
      validate_readme_links
      errors
    end

    private

    def load_yaml(path, label)
      unless File.file?(path)
        errors << "#{label}: missing #{relative(path)}"
        return nil
      end

      YAML.safe_load(File.read(path), permitted_classes: [], aliases: true)
    rescue Psych::SyntaxError => e
      errors << "#{label}: invalid YAML: #{e.message}"
      nil
    end

    def validate_manifest_shape
      errors << "manifest: schema_version must be 1" unless manifest["schema_version"] == 1
      errors << "manifest: skills must be a mapping" unless manifest["skills"].is_a?(Hash)
    end

    def validate_entries
      readme = readme_text

      skills.each do |name, entry|
        unless name.length.between?(1, 64) && NAME_PATTERN.match?(name)
          errors << "#{name}: name must use lowercase alphanumeric words separated by single hyphens"
        end

        unless entry.is_a?(Hash)
          errors << "#{name}: manifest entry must be a mapping"
          next
        end

        REQUIRED_FIELDS.each do |field|
          errors << "#{name}: missing manifest field #{field}" if blank?(entry[field])
        end

        errors << "#{name}: invalid class #{entry['class'].inspect}" unless ALLOWED_CLASSES.include?(entry["class"])
        targets = Array(entry["targets"])
        errors << "#{name}: targets must not be empty" if targets.empty?
        invalid_targets = targets - ALLOWED_TARGETS
        errors << "#{name}: invalid targets #{invalid_targets.join(', ')}" unless invalid_targets.empty?
        errors << "#{name}: ownership must be first-party" unless entry["ownership"] == "first-party"
        errors << "#{name}: publication must be public" unless entry["publication"] == "public"
        validate_routing(name, entry, targets)

        path = safe_skill_path(name, entry["path"])
        next unless path

        skill_file = File.join(path, "SKILL.md")
        unless File.file?(skill_file)
          errors << "#{name}: missing #{relative(skill_file)}"
          next
        end

        validate_skill_file(name, skill_file)
        validate_openai_metadata(name, path)
        link = "[`#{name}`](#{entry['path']}/SKILL.md)"
        errors << "#{name}: missing README catalog link" unless readme.include?(link)
      end
    end

    def validate_routing(name, entry, targets)
      if entry["class"] == "portable" && targets != ["agents"]
        errors << "#{name}: portable skills must target only agents"
      elsif entry["class"] == "codex" && targets != ["codex"]
        errors << "#{name}: Codex skills must target only codex"
      end

      if entry["class"] == "codex" && !entry["path"].to_s.start_with?("platforms/codex/")
        errors << "#{name}: Codex skills must live under platforms/codex"
      end
    end

    def safe_skill_path(name, declared_path)
      return nil if blank?(declared_path)

      expanded = File.expand_path(declared_path, root)
      unless expanded.start_with?("#{root}/")
        errors << "#{name}: path escapes repository root"
        return nil
      end
      expanded
    end

    def validate_skill_file(name, path)
      text = File.read(path)
      frontmatter = text[/\A---\n(.*?)\n---/m, 1]
      unless frontmatter
        errors << "#{name}: missing YAML frontmatter"
        return
      end

      data = YAML.safe_load(frontmatter, permitted_classes: [], aliases: false)
      unless data.is_a?(Hash)
        errors << "#{name}: YAML frontmatter must be a mapping"
        return
      end

      errors << "#{name}: frontmatter name does not match manifest" unless data["name"] == name
      errors << "#{name}: missing description" if blank?(data["description"])
      errors << "#{name}: description is over 500 characters" if data["description"].to_s.length > 500
    rescue Psych::SyntaxError => e
      errors << "#{name}: invalid YAML frontmatter: #{e.message}"
    end

    def validate_openai_metadata(name, skill_path)
      path = File.join(skill_path, "agents", "openai.yaml")
      unless File.file?(path)
        errors << "#{name}: missing agents/openai.yaml"
        return
      end

      data = load_yaml(path, name)
      return unless data
      unless data.is_a?(Hash)
        errors << "#{name}: agents/openai.yaml must be a mapping"
        return
      end

      errors << "#{name}: missing interface.display_name" if blank?(data.dig("interface", "display_name"))
      errors << "#{name}: missing interface.short_description" if blank?(data.dig("interface", "short_description"))
      errors << "#{name}: missing interface.default_prompt" if blank?(data.dig("interface", "default_prompt"))
      implicit = data.dig("policy", "allow_implicit_invocation")
      errors << "#{name}: policy.allow_implicit_invocation must be true or false" unless [true, false].include?(implicit)
    end

    def validate_filesystem_coverage
      declared = skills.values.map { |entry| entry["path"] if entry.is_a?(Hash) }.compact.sort
      discovered = Dir.glob(File.join(root, "**", "SKILL.md"), File::FNM_DOTMATCH)
        .reject { |path| ignored_skill_file?(path) }
        .map { |path| relative(File.dirname(path)) }
        .sort

      (discovered - declared).each { |path| errors << "filesystem: undeclared skill path #{path}" }
      (declared - discovered).each { |path| errors << "manifest: missing skill path #{path}" }
    end

    def validate_public_repository_boundary
      vendor_root = File.join(root, "vendor")
      errors << "filesystem: public repository must not contain vendor/" if File.exist?(vendor_root)
      openai_root = File.join(root, ".openai")
      errors << "filesystem: public repository must not contain .openai/" if File.exist?(openai_root)
      superpowers_root = File.join(root, "docs", "superpowers")
      errors << "filesystem: public repository must not contain docs/superpowers/" if File.exist?(superpowers_root)
      public_text_files.each do |path|
        label = relative(path)
        errors << "public-safety: sensitive file #{label} is not allowed" if sensitive_file?(label)
      end
    end

    def validate_public_content
      machine_path = Regexp.new("(?:#{Regexp.escape(File::SEPARATOR)}Users|#{Regexp.escape(File::SEPARATOR)}home)#{Regexp.escape(File::SEPARATOR)}[^#{Regexp.escape(File::SEPARATOR)}\\s]+#{Regexp.escape(File::SEPARATOR)}")
      private_host = Regexp.new("(?:git\\.)?chatgpt-team" + "\\.site", Regexp::IGNORECASE)
      secret_signatures = [
        ["AWS access key", Regexp.new("AKIA" + "[0-9A-Z]{16}")],
        ["GitHub token", Regexp.new("(?:gh[pousr]_" + "[A-Za-z0-9_]{20,}|github" + "_pat_[A-Za-z0-9_]{20,})")],
        ["Google API key", Regexp.new("AIza" + "[0-9A-Za-z_-]{35}")],
        ["OpenAI-style key", Regexp.new("sk-" + "[A-Za-z0-9_-]{20,}")],
        ["private key", Regexp.new("-----BEGIN [A-Z ]*PRIVATE KEY-----")]
      ]

      public_text_files.each do |path|
        text = File.read(path, mode: "r:BOM|UTF-8")
        label = relative(path)
        errors << "public-safety: #{label} contains a machine-specific absolute path" if text.match?(machine_path)
        errors << "public-safety: #{label} contains a private hosting endpoint" if text.match?(private_host)
        secret_signatures.each do |name, pattern|
          errors << "public-safety: #{label} contains a #{name} signature" if text.match?(pattern)
        end
      rescue ArgumentError, Encoding::InvalidByteSequenceError, Encoding::UndefinedConversionError
        next
      end
    end

    def public_text_files
      Dir.glob(File.join(root, "**", "*"), File::FNM_DOTMATCH).select do |path|
        next false unless File.file?(path)

        relative_path = relative(path)
        next false if relative_path.start_with?(".git", ".agent-worktrees/")
        next false if File.size(path) > 1_000_000

        true
      end
    end

    def sensitive_file?(relative_path)
      basename = File.basename(relative_path)
      return true if basename == ".env" || basename.start_with?(".env.")
      return true if %w[.npmrc .pypirc .netrc credentials.json secrets.json tokens.json].include?(basename.downcase)

      %w[.pem .key .p12 .pfx .jks .keystore .mobileprovision].any? do |suffix|
        basename.downcase.end_with?(suffix)
      end
    end

    def ignored_skill_file?(path)
      relative_path = relative(path)
      relative_path.start_with?(".git/", ".agent-worktrees/", "tests/fixtures/")
    end

    def validate_target_collisions
      seen = {}
      skills.each do |name, entry|
        next unless entry.is_a?(Hash)

        Array(entry["targets"]).each do |target|
          key = [target, name]
          errors << "#{name}: duplicate active target #{target}" if seen[key]
          seen[key] = true
        end
      end
    end

    def validate_readme_links
      readme_text.scan(/\]\(([^)]+)\)/).flatten.each do |raw_link|
        link = raw_link.delete_prefix("<").delete_suffix(">")
        next if link.start_with?("#") || link.match?(/\A[a-z][a-z0-9+.-]*:/i)

        target = link.split("#", 2).first
        next if target.empty?

        errors << "README: missing relative link target #{target}" unless File.exist?(File.join(root, target))
      end
    end

    def readme_text
      path = File.join(root, "README.md")
      File.file?(path) ? File.read(path) : ""
    end

    def blank?(value)
      value.nil? || value.respond_to?(:empty?) && value.empty? || value.respond_to?(:strip) && value.strip.empty?
    end

    def relative(path)
      path.delete_prefix("#{root}/")
    end
  end
end
