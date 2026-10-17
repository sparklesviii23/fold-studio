import type {ReactNode} from 'react';

/** Only passive descendants participate in native dragging; controls are siblings. */
export default function WindowChrome({title, subtitle, children}: {
  title: string; subtitle?: string; children?: ReactNode;
}) {
  return <header className="window-chrome" data-tauri-drag-region>
    <div className="window-title-region" data-tauri-drag-region>
      <span data-tauri-drag-region className="window-title-star">✦</span>
      <span data-tauri-drag-region>{title}</span>
      {subtitle && <span data-tauri-drag-region className="window-title-context">{subtitle}</span>}
    </div>
    <div className="window-toolbar-controls">{children}</div>
  </header>;
}
