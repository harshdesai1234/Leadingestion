import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import type { DragEndEvent } from '@dnd-kit/core';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Loader2, Save, Image as ImageIcon, Sparkles, AlertCircle } from 'lucide-react';

interface Section {
  id: number;
  title: string;
  content_html: string;
  order: number;
}

interface Document {
  id: number;
  title: string;
  status: string;
}

const csrfToken = document.cookie
  .split('; ')
  .find((row) => row.startsWith('csrftoken='))
  ?.split('=')[1] || '';

axios.defaults.headers.common['X-CSRFToken'] = csrfToken;

// --- Sortable Item Component ---
function SortableSection({
  section,
  onSave,
  onRegenerate,
}: {
  section: Section;
  onSave: (id: number, content: string, title: string) => void;
  onRegenerate: (id: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: section.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : 1,
  };

  const editor = useEditor({
    extensions: [StarterKit],
    content: section.content_html,
    onUpdate: ({ editor }) => {
      onSave(section.id, editor.getHTML(), section.title);
    },
  });

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6 overflow-hidden relative group"
    >
      <div className="flex items-center gap-2 p-4 border-b border-gray-100 bg-gray-50/50">
        <div {...attributes} {...listeners} className="cursor-grab hover:bg-gray-200 p-1 rounded">
          <GripVertical className="w-5 h-5 text-gray-400" />
        </div>
        <input
          type="text"
          defaultValue={section.title}
          onBlur={(e) => onSave(section.id, editor?.getHTML() || '', e.target.value)}
          className="font-medium text-lg bg-transparent border-none focus:ring-0 focus:outline-none p-0 flex-1"
        />
        <button
          onClick={() => onRegenerate(section.id)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors"
        >
          <Sparkles className="w-4 h-4" />
          Regenerate
        </button>
      </div>

      <div className="p-6 prose max-w-none">
        <EditorContent editor={editor} className="min-h-[100px] outline-none" />
      </div>
    </div>
  );
}

// --- Main Editor Component ---
export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<Document | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiImageLoading, setAiImageLoading] = useState(false);
  
  const autoSaveTimeoutRef = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    const fetchDocument = async () => {
      try {
        const res = await axios.get(`/proposals/api/documents/${id}/`);
        setDoc(res.data.document);
        setSections(res.data.sections);
        setIsGenerating(res.data.document.status === 'GENERATING');
      } catch (err) {
        console.error('Failed to fetch document', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchDocument();
  }, [id]);

  useEffect(() => {
    let pollInterval: ReturnType<typeof setInterval>;
    
    const checkJobStatus = async () => {
      try {
        const res = await axios.get(`/proposals/api/documents/${id}/`);
        if (res.data.document.status !== 'GENERATING') {
          setIsGenerating(false);
          setDoc(res.data.document);
          setSections(res.data.sections);
        }
      } catch (err) {
        console.error(err);
      }
    };

    if (isGenerating) {
      pollInterval = setInterval(checkJobStatus, 3000);
    }
    return () => clearInterval(pollInterval);
  }, [isGenerating, id]);

  const handleAutoSave = useCallback((sectionId: number, content: string, title: string) => {
    if (autoSaveTimeoutRef.current[sectionId]) {
      clearTimeout(autoSaveTimeoutRef.current[sectionId]);
    }

    setSections((prev) =>
      prev.map((s) => (s.id === sectionId ? { ...s, content_html: content, title } : s))
    );

    setSaveStatus('Saving...');

    autoSaveTimeoutRef.current[sectionId] = setTimeout(async () => {
      try {
        const formData = new FormData();
        formData.append('content_html', content);
        formData.append('title', title);
        await axios.post(`/proposals/${id}/section/${sectionId}/save/`, formData);
        setSaveStatus('Saved');
        setTimeout(() => setSaveStatus(null), 2000);
      } catch (err) {
        console.error('Failed to autosave section', err);
        setSaveStatus('Error saving');
      }
    }, 1000);
  }, [id]);

  const handleSaveAll = async () => {
    setSaving(true);
    setSaveStatus('Saving all...');
    try {
      const payload = {
        sections: sections.map(s => ({
          id: s.id,
          title: s.title,
          content_html: s.content_html
        }))
      };
      await axios.post(`/proposals/${id}/section/save-all/`, payload);
      setSaveStatus('All changes saved');
      setTimeout(() => setSaveStatus(null), 2000);
    } catch (err) {
      console.error('Save all failed', err);
      setSaveStatus('Error saving all');
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateSection = async (sectionId: number) => {
    try {
      await axios.post(`/proposals/${id}/section/${sectionId}/regenerate/`);
      // Since regenerate is async in backend (creates AIJob), we might want to poll or refetch
      setIsGenerating(true);
    } catch (err) {
      console.error('Failed to regenerate section', err);
    }
  };

  const handleGenerateImage = async () => {
    const selection = window.getSelection();
    const prompt = selection?.toString().trim();
    if (!prompt) {
      alert('Please select some text to generate an image.');
      return;
    }

    setAiImageLoading(true);
    try {
      const formData = new FormData();
      formData.append('prompt', prompt);
      formData.append('document_id', id!);
      const res = await axios.post(`/proposals/api/generate-image/`, formData);
      
      const imgUrl = res.data.image_url || res.data.url;
      if (imgUrl) {
        document.execCommand('insertHTML', false, `<img src="${imgUrl}" alt="AI Generated" class="my-4 max-w-full rounded-lg" />`);
      }
    } catch (err) {
      console.error('AI image generation failed', err);
      alert('Failed to generate image.');
    } finally {
      setAiImageLoading(false);
    }
  };

  // DND Kit Setup
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      let newSections: Section[] = [];
      setSections((items) => {
        const oldIndex = items.findIndex((i) => i.id === active.id);
        const newIndex = items.findIndex((i) => i.id === over.id);
        newSections = arrayMove(items, oldIndex, newIndex);
        return newSections;
      });

      try {
        await axios.post(`/proposals/${id}/section/reorder/`, {
          section_ids: newSections.map(s => s.id)
        });
      } catch (err) {
        console.error('Failed to reorder', err);
      }
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-gray-900">{doc?.title || 'Document Editor'}</h1>
          {isGenerating && (
            <span className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 px-3 py-1 rounded-full border border-amber-200">
              <Loader2 className="w-4 h-4 animate-spin" />
              AI is working...
            </span>
          )}
          {saveStatus && !isGenerating && (
            <span className="text-sm text-gray-500">{saveStatus}</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerateImage}
            disabled={aiImageLoading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {aiImageLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImageIcon className="w-4 h-4" />}
            AI Image
          </button>
          
          <button
            onClick={handleSaveAll}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save All
          </button>
        </div>
      </header>

      {/* Main Content Workspace */}
      <main className="max-w-4xl mx-auto mt-8 px-4">
        {sections.length === 0 && !isGenerating ? (
          <div className="text-center py-12 bg-white rounded-lg border border-dashed border-gray-300">
            <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No sections found</h3>
            <p className="mt-1 text-gray-500">This document doesn't have any sections yet.</p>
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={sections.map((s) => s.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-6">
                {sections.map((section) => (
                  <SortableSection
                    key={section.id}
                    section={section}
                    onSave={handleAutoSave}
                    onRegenerate={handleRegenerateSection}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </main>
    </div>
  );
}
