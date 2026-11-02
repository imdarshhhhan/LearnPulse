# Student Folders

The `/folders` route gives authenticated students a private library for organizing study materials.

## Structure

- `page.tsx` checks the saved student role, loads folders, and coordinates folder and file API actions.
- `components/FolderList.tsx` renders folders and the create-folder form.
- `components/FolderContents.tsx` handles the selected folder's materials, upload, preview, download, rename, and delete controls.
- `folders.module.css` contains styles scoped to the feature.
- `services/foldersApi.ts` contains the frontend API client.

## Backend and access control

The frontend calls the `/social/folders` API. Every endpoint requires a JWT and checks that the account role is `student`. Folder and document queries always include the authenticated student's ownership; missing or other students' IDs return `404`.

File bytes are stored under the backend's `FOLDER_STORAGE_DIR` (defaults to `app/folder_storage`, which is ignored by Git). The database stores the file name, media type, byte size, and opaque storage key. Uploads are limited to 10 MB and validated against supported PDF, image, text, CSV, Markdown, and DOCX formats.
