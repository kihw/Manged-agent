import type { ProjectSummary } from "../types";

interface ProjectRailProps {
  projects: ProjectSummary[];
  selectedProjectId: string;
  onSelectProject: (projectId: string) => void;
}

export function ProjectRail({ projects, selectedProjectId, onSelectProject }: ProjectRailProps) {
  return (
    <aside className="project-rail">
      <div className="rail-header">
        <span className="eyebrow">Projets</span>
        <h2>Focus</h2>
      </div>
      <button
        className={`project-chip ${selectedProjectId === "all" ? "selected" : ""}`}
        onClick={() => onSelectProject("all")}
        type="button"
      >
        <span>Tous les projets</span>
        <strong>{projects.reduce((sum, project) => sum + project.run_count, 0)}</strong>
      </button>
      {projects.map((project) => (
        <button
          key={project.project_id}
          className={`project-chip ${selectedProjectId === project.project_id ? "selected" : ""}`}
          onClick={() => onSelectProject(project.project_id)}
          type="button"
        >
          <div>
            <span>{project.display_name}</span>
            <small>{project.workspace_path}</small>
          </div>
          <strong>{project.run_count}</strong>
        </button>
      ))}
    </aside>
  );
}
