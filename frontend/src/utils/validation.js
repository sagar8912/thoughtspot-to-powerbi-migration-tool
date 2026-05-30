import { config } from '../config.js';

/**
 * File validation utilities
 * Provides validation for file uploads (type, size, count)
 */

/**
 * Validates a single file
 * @param {File} file - File object to validate
 * @returns {Object} - { valid: boolean, error: string | null }
 */
export const validateFile = (file) => {
  // Check file extension
  const fileName = file.name.toLowerCase();
  const hasValidExtension = config.allowedExtensions.some(ext =>
    fileName.endsWith(ext)
  );

  if (!hasValidExtension) {
    return {
      valid: false,
      error: `File '${file.name}' is not a valid Excel file. Allowed types: ${config.allowedExtensions.join(', ')}`
    };
  }

  // Check file size
  if (file.size > config.maxFileSize) {
    const maxSizeMB = Math.round(config.maxFileSize / (1024 * 1024));
    const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
    return {
      valid: false,
      error: `File '${file.name}' (${fileSizeMB}MB) exceeds the maximum size of ${maxSizeMB}MB`
    };
  }

  // Check if file is empty
  if (file.size === 0) {
    return {
      valid: false,
      error: `File '${file.name}' is empty`
    };
  }

  return { valid: true, error: null };
};

/**
 * Validates multiple files
 * @param {FileList|Array} files - Files to validate
 * @returns {Object} - { valid: boolean, errors: string[], validFiles: File[] }
 */
export const validateFiles = (files) => {
  const filesArray = Array.from(files);
  const errors = [];
  const validFiles = [];

  // Check file count
  if (filesArray.length === 0) {
    return {
      valid: false,
      errors: ['No files selected'],
      validFiles: []
    };
  }

  if (filesArray.length > config.maxFiles) {
    return {
      valid: false,
      errors: [`Maximum ${config.maxFiles} files allowed. You selected ${filesArray.length} files.`],
      validFiles: []
    };
  }

  // Validate each file
  filesArray.forEach(file => {
    const validation = validateFile(file);
    if (validation.valid) {
      validFiles.push(file);
    } else {
      errors.push(validation.error);
    }
  });

  return {
    valid: errors.length === 0,
    errors,
    validFiles
  };
};

/**
 * Calculates total size of files
 * @param {FileList|Array} files - Files to calculate size for
 * @returns {number} - Total size in bytes
 */
export const getTotalFileSize = (files) => {
  return Array.from(files).reduce((total, file) => total + file.size, 0);
};

/**
 * Formats file size to human-readable string
 * @param {number} bytes - Size in bytes
 * @returns {string} - Formatted size (e.g., "2.5 MB")
 */
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${units[i]}`;
};

/**
 * Checks if file type is supported
 * @param {string} fileName - File name to check
 * @returns {boolean} - True if supported
 */
export const isSupportedFileType = (fileName) => {
  const lowerCaseName = fileName.toLowerCase();
  return config.allowedExtensions.some(ext => lowerCaseName.endsWith(ext));
};

/**
 * Validates file name for special characters
 * @param {string} fileName - File name to validate
 * @returns {Object} - { valid: boolean, error: string | null }
 */
export const validateFileName = (fileName) => {
  // Check for invalid characters
  const invalidChars = /[<>:"|?*]/;
  if (invalidChars.test(fileName)) {
    return {
      valid: false,
      error: `File name '${fileName}' contains invalid characters`
    };
  }

  // Check file name length
  if (fileName.length > 255) {
    return {
      valid: false,
      error: `File name '${fileName}' is too long (max 255 characters)`
    };
  }

  return { valid: true, error: null };
};

/**
 * Checks if files array contains duplicates
 * @param {FileList|Array} files - Files to check
 * @returns {Array} - Array of duplicate file names
 */
export const findDuplicateFiles = (files) => {
  const filesArray = Array.from(files);
  const fileNames = filesArray.map(f => f.name);
  const duplicates = fileNames.filter(
    (name, index) => fileNames.indexOf(name) !== index
  );

  return [...new Set(duplicates)]; // Return unique duplicates
};
