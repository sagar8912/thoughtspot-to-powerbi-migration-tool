/**
 * Formatting utilities
 * Provides consistent formatting for dates, numbers, and other data types
 */

/**
 * Formats a date string to a human-readable format
 * @param {string|Date} date - Date to format
 * @param {string} format - Format type ('short', 'long', 'time', 'datetime')
 * @returns {string} - Formatted date string
 */
export const formatDate = (date, format = 'short') => {
  if (!date) return '-';

  const dateObj = typeof date === 'string' ? new Date(date) : date;

  if (isNaN(dateObj.getTime())) {
    return 'Invalid date';
  }

  const options = {
    short: { year: 'numeric', month: 'short', day: 'numeric' },
    long: { year: 'numeric', month: 'long', day: 'numeric' },
    time: { hour: '2-digit', minute: '2-digit', second: '2-digit' },
    datetime: {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }
  };

  return new Intl.DateTimeFormat('en-US', options[format] || options.short).format(dateObj);
};

/**
 * Formats a number to a human-readable string
 * @param {number} num - Number to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} - Formatted number string
 */
export const formatNumber = (num, decimals = 0) => {
  if (num === null || num === undefined) return '-';
  if (isNaN(num)) return 'Invalid number';

  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(num);
};

/**
 * Formats a percentage
 * @param {number} value - Value to format (0-100)
 * @param {number} decimals - Number of decimal places
 * @returns {string} - Formatted percentage string
 */
export const formatPercentage = (value, decimals = 1) => {
  if (value === null || value === undefined) return '-';
  if (isNaN(value)) return 'Invalid percentage';

  return `${formatNumber(value, decimals)}%`;
};

/**
 * Formats a file size to human-readable string
 * @param {number} bytes - Size in bytes
 * @param {number} decimals - Number of decimal places
 * @returns {string} - Formatted size (e.g., "2.5 MB")
 */
export const formatFileSize = (bytes, decimals = 2) => {
  if (bytes === 0) return '0 B';
  if (!bytes) return '-';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
};

/**
 * Formats elapsed time duration
 * @param {number} seconds - Duration in seconds
 * @returns {string} - Formatted duration (e.g., "2m 30s")
 */
export const formatDuration = (seconds) => {
  if (seconds === null || seconds === undefined || seconds < 0) return '-';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
};

/**
 * Formats elapsed time in short format
 * @param {number} seconds - Duration in seconds
 * @returns {string} - Formatted duration (e.g., "2:30")
 */
export const formatDurationShort = (seconds) => {
  if (seconds === null || seconds === undefined || seconds < 0) return '-';

  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);

  return `${minutes}:${secs.toString().padStart(2, '0')}`;
};

/**
 * Formats a confidence level to display text
 * @param {string} level - Confidence level ('HIGH', 'MEDIUM', 'LOW')
 * @returns {Object} - { text: string, color: string, icon: string }
 */
export const formatConfidenceLevel = (level) => {
  const levels = {
    HIGH: {
      text: 'High Confidence',
      color: 'text-green-700',
      bgColor: 'bg-green-100',
      borderColor: 'border-green-300',
      icon: '✓'
    },
    MEDIUM: {
      text: 'Medium Confidence',
      color: 'text-orange-700',
      bgColor: 'bg-orange-100',
      borderColor: 'border-orange-300',
      icon: '~'
    },
    LOW: {
      text: 'Low Confidence',
      color: 'text-gray-700',
      bgColor: 'bg-gray-100',
      borderColor: 'border-gray-300',
      icon: '?'
    }
  };

  return levels[level] || levels.LOW;
};

/**
 * Formats a relationship type to display text
 * @param {string} type - Relationship type
 * @returns {string} - Formatted type
 */
export const formatRelationshipType = (type) => {
  if (!type) return '-';

  // Convert snake_case to Title Case
  return type
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

/**
 * Formats a job status to display text with color
 * @param {string} status - Job status
 * @returns {Object} - { text: string, color: string, bgColor: string }
 */
export const formatJobStatus = (status) => {
  const statuses = {
    pending: {
      text: 'Pending',
      color: 'text-gray-700',
      bgColor: 'bg-gray-100',
      borderColor: 'border-gray-300'
    },
    running: {
      text: 'Running',
      color: 'text-blue-700',
      bgColor: 'bg-blue-100',
      borderColor: 'border-blue-300'
    },
    completed: {
      text: 'Completed',
      color: 'text-green-700',
      bgColor: 'bg-green-100',
      borderColor: 'border-green-300'
    },
    failed: {
      text: 'Failed',
      color: 'text-red-700',
      bgColor: 'bg-red-100',
      borderColor: 'border-red-300'
    }
  };

  return statuses[status] || statuses.pending;
};

/**
 * Truncates text to a maximum length
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} - Truncated text with ellipsis
 */
export const truncateText = (text, maxLength = 50) => {
  if (!text) return '';
  if (text.length <= maxLength) return text;

  return `${text.substring(0, maxLength)}...`;
};

/**
 * Formats a data type to display icon
 * @param {string} dataType - Data type ('string', 'number', 'date', 'boolean')
 * @returns {string} - Icon emoji
 */
export const getDataTypeIcon = (dataType) => {
  const icons = {
    string: '📝',
    text: '📝',
    number: '🔢',
    integer: '🔢',
    float: '🔢',
    date: '📅',
    datetime: '📅',
    boolean: '✓',
    bool: '✓'
  };

  return icons[dataType?.toLowerCase()] || '•';
};

/**
 * Formats a large number with K, M, B suffixes
 * @param {number} num - Number to format
 * @returns {string} - Formatted number (e.g., "1.2K", "3.5M")
 */
export const formatLargeNumber = (num) => {
  if (num === null || num === undefined) return '-';
  if (isNaN(num)) return 'Invalid number';

  if (num >= 1000000000) {
    return (num / 1000000000).toFixed(1) + 'B';
  }
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }

  return num.toString();
};

/**
 * Formats a timestamp to relative time (e.g., "2 hours ago")
 * @param {string|Date} date - Date to format
 * @returns {string} - Relative time string
 */
export const formatRelativeTime = (date) => {
  if (!date) return '-';

  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffInSeconds = Math.floor((now - dateObj) / 1000);

  if (diffInSeconds < 60) {
    return 'Just now';
  } else if (diffInSeconds < 3600) {
    const minutes = Math.floor(diffInSeconds / 60);
    return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
  } else if (diffInSeconds < 86400) {
    const hours = Math.floor(diffInSeconds / 3600);
    return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  } else {
    const days = Math.floor(diffInSeconds / 86400);
    return `${days} day${days > 1 ? 's' : ''} ago`;
  }
};
