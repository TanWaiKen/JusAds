interface FilterItem {
  label: string;
  value: string;
}

interface FilterBarProps {
  filters: FilterItem[];
  active: string;
  onChange: (value: string) => void;
}

/**
 * Row of pill-shaped filter buttons with active/inactive states.
 * Active: bg-text-primary dark:bg-white text-white dark:text-text-primary
 * Inactive: bg-gray-100 dark:bg-white/5 text-gray-500 hover:bg-gray-200 dark:hover:bg-white/10
 */
export function FilterBar({ filters, active, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {filters.map((filter) => {
        const isActive = filter.value === active;
        return (
          <button
            key={filter.value}
            type="button"
            onClick={() => onChange(filter.value)}
            className={
              isActive
                ? "rounded-full px-4 py-1.5 text-sm font-medium transition-colors bg-text-primary text-white dark:bg-white dark:text-text-primary"
                : "rounded-full px-4 py-1.5 text-sm font-medium transition-colors bg-gray-100 text-gray-500 hover:bg-gray-200 dark:bg-white/5 dark:hover:bg-white/10"
            }
          >
            {filter.label}
          </button>
        );
      })}
    </div>
  );
}
