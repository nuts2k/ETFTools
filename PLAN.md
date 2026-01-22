# Confirmation Dialog Implementation Plan

## Goal
Replace the native `window.confirm()` dialog in the Settings page with a custom, polished modal that matches the app's "App Shell" design language.

## 1. Create Component: `ConfirmationDialog`
**File**: `frontend/components/ConfirmationDialog.tsx`

**Specs**:
- **Backdrop**: Fixed overlay with `bg-black/50` and `backdrop-blur-sm`.
- **Container**: Centered, `rounded-xl`, `bg-card`, `shadow-2xl`.
- **Content**:
  - Title (Bold, Large)
  - Description (Muted, Small)
  - Action Buttons (Cancel / Confirm)
- **Props**:
  - `isOpen`: boolean
  - `title`: string
  - `description`: string
  - `confirmLabel`: string (default: "Confirm")
  - `cancelLabel`: string (default: "Cancel")
  - `onConfirm`: () => void
  - `onCancel`: () => void
  - `variant`: 'default' | 'destructive' (affects Confirm button color)

## 2. Update Settings Page
**File**: `frontend/app/settings/page.tsx`

**Changes**:
- Import `ConfirmationDialog`.
- Add state: `const [showClearCacheDialog, setShowClearCacheDialog] = useState(false)`.
- Replace `confirm()` logic:
  - Button click sets `showClearCacheDialog(true)`.
  - Dialog `onConfirm` calls `localStorage.clear()` and reload.
- Render the dialog component at the bottom of the JSX.

## 3. Styling Details
- **Confirm Button (Destructive)**: `bg-destructive text-destructive-foreground`
- **Cancel Button**: `bg-secondary text-secondary-foreground`
- **Animation**: Simple opacity/scale transition (optional, or use conditional rendering).

## 4. Verification
- Verify dialog appears on "Clear Cache" click.
- Verify "Cancel" closes dialog without action.
- Verify "Confirm" clears storage and reloads page.
- Check dark mode compatibility.
