import getpass
import json
import pkg_resources

from trac.admin import IAdminPanelProvider
from trac.core import *
from trac.config import Option, BoolOption
from trac.util.translation import _
from trac.web.chrome import ITemplateProvider
from trac.web.chrome import add_notice
from trac.web.chrome import add_warning

from trac_gitolite import utils

class GitolitePermissionManager(Component):
    implements(IAdminPanelProvider, ITemplateProvider)

    gitolite_admin_reponame = Option('trac-gitolite', 'admin_reponame',
                                     default="gitolite-admin")
    gitolite_admin_ssh_path = Option('trac-gitolite', 'admin_ssh_path',
                                     default="git@localhost:gitolite-admin.git")
    gitolite_admin_real_reponame = Option('trac-gitolite', 'admin_real_reponame',
                                          default="gitolite-admin")
    gitolite_admin_system_user = Option('trac-gitolite', 'admin_system_user',
                                        default="trac")

    def get_users(self):
        node = utils.get_repo_node(self.env, self.gitolite_admin_reponame, 
                                   "keydir")
        assert node.isdir, "Node %s at /keydir/ is not a directory" % node
        for child in node.get_entries():
            name = child.get_name()
            assert name.endswith(".pub"), "Node %s" % name
            name = name[:-4]
            if name.endswith('@rsa'):
                name = name[:-4]
            if name not in res:
                res.append(name)
            #yield name
        return res

    def read_config(self):
        node = utils.get_repo_node(self.env, self.gitolite_admin_reponame,
                                   "conf/gitolite.conf")
        fp = node.get_content()
        return utils.read_config(self.env,fp)
    
    ## IAdminPanelProvider methods

    def get_admin_panels(self, req):
        if 'VERSIONCONTROL_ADMIN' in req.perm:
            yield ('versioncontrol', _('Version Control'), 'gitolite_permissions', 
                   _('Gitolite Permissions'))

    def render_admin_panel(self, req, category, page, path_info):
        req.perm.require('VERSIONCONTROL_ADMIN')

        if req.method == 'POST':
            perms_old, groups, inverse_groups = self.read_config()
            perms = {}
            for setting in req.args:
                try:
                    setting = json.loads(setting)
                except ValueError:
                    continue
                if not isinstance(setting, dict) or 'perm' not in setting or 'user' not in setting or 'repo' not in setting:
                    continue
                repo = setting['repo']; perm = setting['perm']; user = setting['user']
                if repo not in perms:
                    perms[repo] = {}
                if perm not in perms[repo]:
                    perms[repo][perm] = []
                if user not in perms[repo][perm]:
                    perms[repo][perm].append(user)

            perms[self.gitolite_admin_real_reponame] = perms_old.get(self.gitolite_admin_real_reponame, {})
            gitolite_admin_perms = perms.get(self.gitolite_admin_real_reponame, {})
            if (self.gitolite_admin_system_user not in gitolite_admin_perms.get('R', []) or
                self.gitolite_admin_system_user not in gitolite_admin_perms.get('W', [])):
                add_warning(req, _('Read and write permissions on the gitolite admin repo must not be revoked for user %s -- otherwise this plugin will no longer work!' % self.gitolite_admin_system_user))
                req.redirect(req.href.admin(category, page))

            utils.save_file(self.gitolite_admin_ssh_path, 'conf/gitolite.conf', 
                            utils.to_string(perms, groups),
                            _('Updating repository permissions'))

            add_notice(req, _('The permissions have been updated.'))
            req.redirect(req.href.admin(category, page))

        perms, groups, inverse_groups = self.read_config()

        users_listed_in_perms = set()
        for perm in perms.values():
            for userlist in perm.values():
                users_listed_in_perms.update(userlist)
        users = sorted(list(set(list(self.get_users()) + list(users_listed_in_perms) + groups.keys() + ['@all'])))

        repos_perms = {}
        for repo in perms:
            if repo != "gitolite-admin":
                users_listed_in_perms = set()
                if repo not in repos_perms:
                    repos_perms[repo] = {}
                    for permission_class in ("W", "R", "0"):
                        repos_perms[repo][permission_class] = {"g": [], "u": []}
                    repos_perms[repo]["perms"] = perms[repo]

                for permission_class in ("W", "R"):
                    for user in perms[repo].get(permission_class, []):
                        if user not in users_listed_in_perms:
                            if user.startswith("@"):
                                repos_perms[repo][permission_class]["g"].append(user)
                            else:
                                repos_perms[repo][permission_class]["u"].append(user)
                            users_listed_in_perms.add(user)
                for user in users:
                    if user not in users_listed_in_perms:
                        if user.startswith("@"):
                            repos_perms[repo]["0"]["g"].append(user)
                        else:
                            repos_perms[repo]["0"]["u"].append(user)

        flattened_perms = set()
        for p in perms.values():
            for perm in p:
                flattened_perms.add(perm)
        flattened_perms = list(flattened_perms)
        def sort_perms(perms):
            tail = []
            ## Ensure the + goes last
            if '+' in perms:
                perms.remove("+")
                tail.append("+")
            perms = sorted(perms)
            perms.extend(tail)
            return perms
        flattened_perms = sort_perms(flattened_perms)

        data = {'permissions': flattened_perms, 
                'repos_perms': repos_perms,
                'groups': groups,
                'inverse_groups': inverse_groups}
        return 'admin_repository_permissions.html', data

    # ITemplateProvider methods

    def get_htdocs_dirs(self):
        return []

    def get_templates_dirs(self):
        return [pkg_resources.resource_filename('trac_gitolite', 'templates')]
