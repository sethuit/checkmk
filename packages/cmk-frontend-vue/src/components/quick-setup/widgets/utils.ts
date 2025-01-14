import TextWidget from '@/components/quick-setup/widgets/TextWidget.vue'
import NoteTextWidget from '@/components/quick-setup/widgets/NoteTextWidget.vue'
import ListWidget from '@/components/quick-setup/widgets/ListWidget.vue'
import NoneWidget from '@/components/quick-setup/widgets/NoneWidget.vue'
import FormSpecWidget from '@/components/quick-setup/widgets/FormSpecWidget.vue'
import CollapsibleWidget from '@/components/quick-setup/widgets/CollapsibleWidget.vue'

export const getWidget = (widgetType: string): unknown => {
  //<component :is="getWidget(widgetType)" v-bind="widget_props" @update="update_data" />
  const map: Record<string, unknown> = {
    text: TextWidget,
    note_text: NoteTextWidget,
    list_of_widgets: ListWidget,
    form_spec: FormSpecWidget,
    collapsible: CollapsibleWidget
  }

  return widgetType in map ? map[widgetType] : NoneWidget
}
