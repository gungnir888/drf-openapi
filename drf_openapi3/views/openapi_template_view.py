from django.views.generic import TemplateView

class OpenApiTemplateView(TemplateView):
    template_name = "openapi-ui.html"
    title= "OpenAPI REST API"

    def get_context_data(self, **kwargs):
        context = super(OpenApiTemplateView, self).get_context_data(**kwargs)
        context["title"] = self.title
        return context