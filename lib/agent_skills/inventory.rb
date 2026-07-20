# frozen_string_literal: true

require "digest"

module AgentSkills
  class Inventory
    IGNORED_HASH_DIRECTORIES = %w[
      __pycache__ .pytest_cache .mypy_cache .ruff_cache .venv venv
      node_modules .npm .pnpm-store tmp temp local exports
    ].freeze
    IGNORED_HASH_FILES = [".DS_Store"].freeze
    IGNORED_HASH_SUFFIXES = %w[.pyc .pyo .pyd .log .tmp .temp .zip .tar .tar.gz .tgz].freeze

    attr_reader :catalog, :roots

    def initialize(catalog, roots)
      @catalog = catalog
      @roots = roots.transform_keys(&:to_s).transform_values { |path| File.expand_path(path) }
    end

    def repository
      catalog.skills.sort.map do |name, entry|
        source = File.expand_path(entry.fetch("path"), catalog.root)
        {
          "name" => name,
          "class" => entry.fetch("class"),
          "target" => Array(entry.fetch("targets")).first,
          "source_path" => source,
          "content_sha256" => directory_hash(source)
        }
      end
    end

    def statuses
      repository.map do |skill|
        destination = File.join(roots.fetch(skill.fetch("target")), skill.fetch("name"))
        state = if !File.directory?(destination)
          "missing"
        elsif directory_hash(destination) == skill.fetch("content_sha256")
          "current"
        else
          "drifted"
        end

        skill.merge("destination" => destination, "state" => state)
      end
    end

    def warnings
      expected_targets = repository.to_h { |skill| [skill.fetch("name"), skill.fetch("target")] }

      roots.sort.flat_map do |target, root|
        installed_skill_names(root).map do |name|
          expected_target = expected_targets[name]
          if expected_target.nil?
            { "kind" => "unmanaged", "target" => target, "name" => name, "path" => File.join(root, name) }
          elsif expected_target != target
            {
              "kind" => "duplicate",
              "target" => target,
              "expected_target" => expected_target,
              "name" => name,
              "path" => File.join(root, name)
            }
          end
        end.compact
      end
    end

    def summary
      counts = { "current" => 0, "missing" => 0, "drifted" => 0 }
      statuses.each { |skill| counts[skill.fetch("state")] += 1 }
      counts["unmanaged"] = warnings.count { |warning| warning.fetch("kind") == "unmanaged" }
      counts["duplicates"] = warnings.count { |warning| warning.fetch("kind") == "duplicate" }
      counts
    end

    def plan
      statuses.map do |skill|
        case skill.fetch("state")
        when "missing"
          action_for("add", skill)
        when "drifted"
          action_for("blocked_drift", skill)
        end
      end.compact
    end

    private

    def action_for(action, skill)
      {
        "action" => action,
        "target" => skill.fetch("target"),
        "name" => skill.fetch("name"),
        "source" => skill.fetch("source_path"),
        "destination" => skill.fetch("destination")
      }
    end

    def installed_skill_names(root)
      return [] unless File.directory?(root)

      Dir.children(root).select do |name|
        File.file?(File.join(root, name, "SKILL.md"))
      end.sort
    end

    def directory_hash(path)
      digest = Digest::SHA256.new
      files = Dir.glob(File.join(path, "**", "*"), File::FNM_DOTMATCH)
        .select { |candidate| File.file?(candidate) && !ignored_hash_file?(candidate, path) }
        .sort

      files.each do |file|
        relative = file.delete_prefix("#{path}/")
        digest << relative << "\0" << File.binread(file) << "\0"
      end
      digest.hexdigest
    end

    def ignored_hash_file?(file, root)
      relative = file.delete_prefix("#{root}/")
      components = relative.split(File::SEPARATOR)
      basename = components.last

      return true unless (components & IGNORED_HASH_DIRECTORIES).empty?
      return true if IGNORED_HASH_FILES.include?(basename)
      return true if basename.include?(".local.")

      IGNORED_HASH_SUFFIXES.any? { |suffix| basename.end_with?(suffix) }
    end
  end
end
