import React, { useState } from 'react';
import { Brain, ChevronRight, CheckCircle, XCircle, AlertTriangle, Code } from 'lucide-react';

const AgentTraceViewer = ({ correctionHistory }) => {
  const [expandedAttempt, setExpandedAttempt] = useState(null);

  if (!correctionHistory || correctionHistory.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
        <Brain className="w-12 h-12 text-gray-400 mx-auto mb-3" />
        <p className="text-sm text-gray-600">No self-healing attempts recorded</p>
        <p className="text-xs text-gray-500 mt-1">The AI will auto-correct if validation fails</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-purple-600" />
            <h3 className="text-lg font-semibold text-gray-900">Self-Healing Agent Trace</h3>
          </div>
          <span className="text-sm text-gray-600">
            {correctionHistory.length} correction attempt{correctionHistory.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Timeline */}
        <div className="space-y-3">
          {correctionHistory.map((attempt, index) => {
            const isExpanded = expandedAttempt === index;
            const isLast = index === correctionHistory.length - 1;

            return (
              <div key={index} className="relative">
                {/* Timeline Line */}
                {!isLast && (
                  <div className="absolute left-6 top-12 bottom-0 w-0.5 bg-gray-200" />
                )}

                <div
                  className={`rounded-lg border-2 transition-all ${
                    isExpanded
                      ? 'border-purple-300 bg-purple-50'
                      : 'border-gray-200 bg-white hover:border-purple-200'
                  }`}
                >
                  {/* Attempt Header */}
                  <button
                    onClick={() => setExpandedAttempt(isExpanded ? null : index)}
                    className="w-full px-4 py-3 flex items-center justify-between text-left"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center">
                        <span className="text-lg font-bold text-purple-700">#{attempt.attempt_number}</span>
                      </div>
                      <div>
                        <div className="font-medium text-gray-900">
                          Attempt {attempt.attempt_number}
                        </div>
                        <div className="text-sm text-gray-600 line-clamp-1">
                          {attempt.root_cause}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {attempt.corrected_dax !== attempt.original_dax ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <XCircle className="w-5 h-5 text-gray-400" />
                      )}
                      <ChevronRight
                        className={`w-5 h-5 text-gray-400 transition-transform ${
                          isExpanded ? 'rotate-90' : ''
                        }`}
                      />
                    </div>
                  </button>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 space-y-4">
                      {/* Root Cause */}
                      <div className="bg-white rounded-lg border border-purple-200 p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <AlertTriangle className="w-4 h-4 text-orange-500" />
                          <span className="text-sm font-medium text-gray-900">Root Cause Analysis</span>
                        </div>
                        <p className="text-sm text-gray-700">{attempt.root_cause}</p>
                      </div>

                      {/* Changes Made */}
                      {attempt.changes_made && attempt.changes_made.length > 0 && (
                        <div className="bg-white rounded-lg border border-purple-200 p-3">
                          <div className="text-sm font-medium text-gray-900 mb-2">Changes Applied</div>
                          <ul className="space-y-1">
                            {attempt.changes_made.map((change, idx) => (
                              <li key={idx} className="text-sm text-gray-700 flex items-start gap-2">
                                <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                                <span>{change}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Code Comparison */}
                      <div className="grid grid-cols-2 gap-3">
                        {/* Original DAX */}
                        <div className="bg-red-50 rounded-lg border border-red-200 p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <Code className="w-4 h-4 text-red-600" />
                            <span className="text-xs font-medium text-red-800">Original (Failed)</span>
                          </div>
                          <pre className="text-xs text-red-900 font-mono whitespace-pre-wrap break-words">
                            {attempt.original_dax}
                          </pre>
                        </div>

                        {/* Corrected DAX */}
                        <div className="bg-green-50 rounded-lg border border-green-200 p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <Code className="w-4 h-4 text-green-600" />
                            <span className="text-xs font-medium text-green-800">Corrected</span>
                          </div>
                          <pre className="text-xs text-green-900 font-mono whitespace-pre-wrap break-words">
                            {attempt.corrected_dax}
                          </pre>
                        </div>
                      </div>

                      {/* Explanation */}
                      {attempt.explanation && (
                        <div className="bg-blue-50 rounded-lg border border-blue-200 p-3">
                          <div className="text-sm font-medium text-blue-900 mb-1">AI Explanation</div>
                          <p className="text-sm text-blue-800">{attempt.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Summary Card */}
      <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg border border-purple-200 p-4">
        <div className="flex items-start gap-3">
          <Brain className="w-6 h-6 text-purple-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-1">Self-Healing Summary</h4>
            <p className="text-sm text-gray-700">
              The AI made <span className="font-bold text-purple-700">{correctionHistory.length}</span> correction
              attempt{correctionHistory.length !== 1 ? 's' : ''} to achieve functional equivalence.
              {correctionHistory.length > 0 && correctionHistory[correctionHistory.length - 1].corrected_dax !==
                correctionHistory[correctionHistory.length - 1].original_dax && (
                <span className="ml-1 text-green-700 font-medium">
                  Final correction applied successfully.
                </span>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentTraceViewer;
